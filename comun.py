"""Conexión con el modelo local y utilidades de las versiones comparadas."""

import json
import unicodedata
from urllib.request import Request, urlopen


MODELO = 'qwen2.5:7b-instruct'
CAMPOS = ('servicio', 'dia', 'hora')
INTENCIONES = {'precio', 'horario', 'ubicacion', 'solicitud', 'otra'}


def consultar_ollama(mensajes, *, json_mode=False):
    payload = {
        'model': MODELO,
        'messages': mensajes,
        'stream': False,
        'keep_alive': '15m',
        'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 256},
    }
    if json_mode:
        payload['format'] = 'json'
    request = Request('http://127.0.0.1:11434/api/chat', json.dumps(payload).encode(),
                      {'Content-Type': 'application/json'})
    with urlopen(request, timeout=180) as response:
        return json.load(response)['message']['content']


def normalizar(valor):
    if valor is None:
        return None
    texto = unicodedata.normalize('NFKD', str(valor).strip().casefold())
    return ''.join(letra for letra in texto if not unicodedata.combining(letra)) or None


def consola(bot):
    print('Peluquería Barrio Sur. Escribe /salir para terminar.')
    while True:
        try:
            mensaje = input('Tú: ').strip()
        except (EOFError, KeyboardInterrupt):
            return
        if mensaje == '/salir':
            return
        if mensaje:
            try:
                print('Peluquería:', bot.responder(mensaje)['respuesta'])
            except OSError as error:
                print(f'Error al acceder al modelo local: {error}')
