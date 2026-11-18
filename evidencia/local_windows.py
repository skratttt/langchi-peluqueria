"""Reproduce la corrida sin HTTP con las DLL de Ollama 0.40.16 en Windows x64."""

import ctypes as C
import hashlib
import os
from pathlib import Path


LIBLLAMA_SHA256 = '8831be8f308bfdd5971a56412814a7eebce2dfc4d504b7944e1a676799313c3e'
MODELO_SHA256 = '2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730'

JSON_GRAMMAR = rb'''
root ::= object
object ::= "{" ws (string ws ":" ws value (ws "," ws string ws ":" ws value)*)? ws "}"
array ::= "[" ws (value (ws "," ws value)*)? ws "]"
value ::= object | array | string | number | "true" | "false" | "null"
string ::= "\"" ([^"\\\x00-\x1f] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""
number ::= "-"? ("0" | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
ws ::= [ \t\n\r]*
'''


# Windows x64 pasa estas estructuras grandes mediante un puntero. Se reserva espacio
# para la estructura nativa completa y se conservan sus valores por defecto tras
# modificar únicamente los campos iniciales verificados para esta DLL.
class ModelParams(C.Structure):
    _fields_ = [('devices', C.c_void_p), ('overrides', C.c_void_p), ('gpu_layers', C.c_int), ('space', C.c_byte * 236)]


class ContextParams(C.Structure):
    _fields_ = [('context', C.c_uint32), ('batch', C.c_uint32), ('ubatch', C.c_uint32), ('seq', C.c_uint32), ('space', C.c_byte * 240)]


class Batch(C.Structure):
    _fields_ = [('n_tokens', C.c_int32), ('token', C.c_void_p), ('embd', C.c_void_p),
                ('pos', C.c_void_p), ('n_seq_id', C.c_void_p), ('seq_id', C.c_void_p), ('logits', C.c_void_p)]


class SamplerParams(C.Structure):
    _fields_ = [('no_perf', C.c_bool)]


class Offline:
    def __init__(self, layers=99):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise OSError('Usa el backend Ollama en este sistema.')
        user = Path.home()
        dlls = Path(os.getenv('LANGCHI_OLLAMA_LIB', user / 'AppData/Local/Programs/Ollama/lib/ollama'))
        dll = dlls / 'libllama.dll'
        if not dll.is_file() or hashlib.sha256(dll.read_bytes()).hexdigest() != LIBLLAMA_SHA256:
            raise OSError('Backend alternativo requiere la DLL original de Ollama 0.40.16. Usa Ollama por HTTP.')
        self.handles = [os.add_dll_directory(str(dlls))]
        if layers:
            self.handles.append(os.add_dll_directory(str(dlls / 'cuda_v12')))
        self.lib = C.CDLL(str(dll))
        ggml = C.CDLL(str(dlls / 'ggml.dll'))
        p, i, b, s = C.c_void_p, C.c_int32, C.c_bool, C.c_char_p

        def bind(name, result, *params):
            f = getattr(self.lib, 'llama_' + name)
            f.restype, f.argtypes = result, params
            setattr(self, name, f)

        bind('backend_init', None)
        bind('model_default_params', ModelParams)
        bind('context_default_params', ContextParams)
        bind('model_load_from_file', p, s, ModelParams)
        bind('init_from_model', p, p, ContextParams)
        bind('model_get_vocab', p, p)
        bind('get_memory', p, p)
        bind('memory_clear', None, p, b)
        bind('memory_seq_rm', b, p, i, i, i)
        bind('tokenize', i, p, s, i, p, i, b, b)
        bind('token_to_piece', i, p, i, p, i, i, b)
        bind('batch_get_one', Batch, p, i)
        bind('decode', i, p, Batch)
        bind('sampler_init_greedy', p)
        bind('sampler_init_grammar', p, p, s, s)
        bind('sampler_chain_init', p, SamplerParams)
        bind('sampler_chain_add', None, p, p)
        bind('sampler_free', None, p)
        bind('sampler_sample', i, p, p, i)
        bind('vocab_is_eog', b, p, i)
        bind('log_set', None, p, p)
        self.log_callback = C.CFUNCTYPE(None, i, s, p)(lambda level, msg, _: None)
        if not os.getenv('LANGCHI_NATIVE_LOG'):
            self.log_set(self.log_callback, None)
        ggml.ggml_backend_load.argtypes = [s]
        ggml.ggml_backend_load.restype = p
        if layers:
            cuda_path = dlls / 'cuda_v12/ggml-cuda.dll'
            self.cuda = C.CDLL(str(cuda_path))
            if not ggml.ggml_backend_load(os.fsencode(cuda_path)):
                raise RuntimeError('No se pudo registrar el backend CUDA')
        ggml.ggml_backend_load(os.fsencode(dlls / 'ggml-cpu-haswell.dll'))
        self.backend_init()
        ollama_models = Path(os.getenv('OLLAMA_MODELS', user / '.ollama/models'))
        model = ollama_models / 'blobs' / f'sha256-{MODELO_SHA256}'
        mp = self.model_default_params()
        mp.gpu_layers = layers
        self.model = self.model_load_from_file(os.fsencode(model), mp)
        if not self.model:
            raise RuntimeError('No se pudo abrir el modelo GGUF')
        cp = self.context_default_params()
        cp.context, cp.batch, cp.ubatch = 8192, 1024, 512
        self.ctx = self.init_from_model(self.model, cp)
        if not self.ctx:
            raise RuntimeError('No se pudo inicializar la inferencia local')
        self.vocab = self.model_get_vocab(self.model)
        self.memory = self.get_memory(self.ctx)
        self.cached = []

    def __call__(self, messages, *, json_mode=False, max_tokens=256):
        text = ''.join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages)
        raw = (text + '<|im_start|>assistant\n').encode()
        tokens = (C.c_int32 * (len(raw) + 16))()
        count = self.tokenize(self.vocab, raw, len(raw), tokens, len(tokens), False, True)
        if count <= 0 or count + max_tokens >= 8192:
            raise ValueError('Longitud de la solicitud fuera del contexto')
        start = 0
        while start < count - 1 and start < len(self.cached) and self.cached[start] == tokens[start]:
            start += 1
        if not start or not self.memory_seq_rm(self.memory, 0, start, -1):
            self.memory_clear(self.memory, False)
            start = 0
        for offset in range(start, count, 1024):
            batch = self.batch_get_one(C.byref(tokens, offset * 4), min(1024, count - offset))
            if self.decode(self.ctx, batch):
                raise RuntimeError('Error al procesar el prompt')
        self.cached = list(tokens[:count])
        parts = []
        piece = C.create_string_buffer(1024)
        sampler = self.sampler_chain_init(SamplerParams(True))
        try:
            if json_mode:
                grammar = self.sampler_init_grammar(self.vocab, JSON_GRAMMAR, b'root')
                if not grammar:
                    raise RuntimeError('No se pudo inicializar la gramática JSON')
                self.sampler_chain_add(sampler, grammar)
            self.sampler_chain_add(sampler, self.sampler_init_greedy())
            for _ in range(max_tokens):
                token = self.sampler_sample(sampler, self.ctx, -1)
                if self.vocab_is_eog(self.vocab, token):
                    break
                size = self.token_to_piece(self.vocab, token, piece, len(piece), 0, False)
                if size > 0:
                    parts.append(piece.raw[:size])
                value = C.c_int32(token)
                if self.decode(self.ctx, self.batch_get_one(C.byref(value), 1)):
                    raise RuntimeError('Error durante la generación')
                self.cached.append(token)
        finally:
            self.sampler_free(sampler)
        return b''.join(parts).decode('utf-8', errors='replace')

