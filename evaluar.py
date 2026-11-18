"""Reproduce los turnos y calcula métricas a partir de respuestas guardadas."""

import argparse
import csv
import hashlib
import importlib
import json
from collections import Counter
from pathlib import Path
import time

from comun import CAMPOS, INTENCIONES, MODELO, consultar_ollama, normalizar


BASE = Path(__file__).resolve().parent
VERSIONES = ('v0', 'v1', 'v2')


def leer_casos(lote):
    conversaciones = {}
    with (BASE / 'pruebas' / f'{lote}.tsv').open(encoding='utf-8', newline='') as file:
        for fila in csv.DictReader(file, delimiter='\t'):
            if None in fila or None in fila.values() or fila['intencion'] not in INTENCIONES:
                raise ValueError(f'Fila inválida: {fila}')
            conversaciones.setdefault(fila['id'], []).append(fila)
    return conversaciones


def ejecutar(version, conversaciones, destino, consultar, backend):
    clase = importlib.import_module(version).Chatbot
    ruta_temporal = destino.with_suffix('.jsonl.tmp')
    llamadas = []

    def registrar_llamada(mensajes, **opciones):
        inicio = time.perf_counter()
        respuesta = consultar(mensajes, **opciones)
        llamadas.append({'texto': respuesta, 'segundos': round(time.perf_counter() - inicio, 3)})
        return respuesta

    with ruta_temporal.open('w', encoding='utf-8', newline='\n') as file:
        for caso, turnos in conversaciones.items():
            bot = clase(consultar=registrar_llamada)
            for numero, fila in enumerate(turnos, start=1):
                inicio = time.perf_counter()
                llamadas.clear()
                registro = {
                    'version': version, 'modelo': MODELO, 'backend': backend, 'id': caso,
                    'grupo': fila['grupo'], 'turno': numero, 'mensaje': fila['mensaje'],
                    'esperado': {'intencion': fila['intencion'],
                                 'datos': {campo: fila[campo] or None for campo in CAMPOS},
                                 'criterio': fila['criterio']},
                }
                try:
                    registro['salida'] = bot.responder(fila['mensaje'])
                except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError) as error:
                    registro['error'] = f'{type(error).__name__}: {error}'
                registro['segundos'] = round(time.perf_counter() - inicio, 3)
                registro['llamadas_modelo'] = list(llamadas)
                file.write(json.dumps(registro, ensure_ascii=False) + '\n')
                file.flush()
            print(f'{version} {caso}', flush=True)
    ruta_temporal.replace(destino)


def leer_salidas(path):
    with path.open(encoding='utf-8') as file:
        return [json.loads(linea) for linea in file]


def medir(registros, revision):
    conteo = Counter()
    casos_con_respuesta = {}
    correcciones = {}
    for registro in registros:
        caso = registro['id']
        salida = registro.get('salida')
        salida = salida if isinstance(salida, dict) else {}
        esperado = registro['esperado']
        tiene_texto = bool(str(salida.get('respuesta') or '').strip())
        casos_con_respuesta[caso] = casos_con_respuesta.get(caso, True) and tiene_texto
        conteo['turnos'] += 1
        conteo['turnos_sin_respuesta'] += not tiene_texto
        conteo['errores_de_ejecucion'] += 'error' in registro
        intencion = normalizar(salida.get('intencion'))
        conteo['intenciones_acertadas'] += intencion == esperado['intencion']
        conteo['intenciones_indeterminadas'] += intencion not in INTENCIONES

        datos = salida.get('datos')
        datos = datos if isinstance(datos, dict) else {}
        esperados = {(campo, normalizar(valor)) for campo, valor in esperado['datos'].items() if valor}
        entregados = {(campo, normalizar(valor)) for campo, valor in datos.items() if normalizar(valor)}
        conteo['pares_esperados'] += len(esperados)
        conteo['pares_correctos'] += len(esperados & entregados)
        conteo['pares_faltantes'] += len(esperados - entregados)
        conteo['pares_incorrectos_o_adicionales'] += len(entregados - esperados)
        conteo['turnos_con_estado_exacto'] += esperados == entregados and tiene_texto
        if registro['grupo'] == 'correccion':
            correcciones[caso] = esperados == entregados and tiene_texto

        huella, etiqueta = revision.get((registro['version'], caso, str(registro['turno'])), (None, None))
        if tiene_texto and etiqueta in {'si', 'no'} and huella == huella_respuesta(salida['respuesta']):
            conteo['respuestas_revisadas'] += 1
            conteo['respuestas_inventadas'] += etiqueta == 'si'
    conteo['conversaciones'] = len(casos_con_respuesta)
    conteo['conversaciones_completadas'] = sum(casos_con_respuesta.values())
    conteo['conversaciones_de_correccion'] = len(correcciones)
    conteo['correcciones_estado_final_correcto'] = sum(correcciones.values())
    conteo['respuestas_revisadas'] += 0
    conteo['respuestas_inventadas'] += 0
    return dict(conteo)


def leer_revision(path):
    if not path.exists():
        return {}
    with path.open(encoding='utf-8', newline='') as file:
        return {(r['version'], r['id'], r['turno']): (r['sha256_respuesta'], r['invencion'])
                for r in csv.DictReader(file, delimiter='\t')}


def huella_respuesta(respuesta):
    return hashlib.sha256(respuesta.encode('utf-8')).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lote', choices=('desarrollo', 'final'), default='desarrollo')
    parser.add_argument('--version', choices=(*VERSIONES, 'todas'), default='todas')
    parser.add_argument('--recalcular', action='store_true', help='Usa las salidas guardadas')
    parser.add_argument('--backend', choices=('ollama', 'libllama-windows'), default='ollama')
    args = parser.parse_args()
    resultados = BASE / 'resultados'
    resultados.mkdir(exist_ok=True)
    versiones = VERSIONES if args.version == 'todas' else (args.version,)
    consultar = consultar_ollama
    if args.backend == 'libllama-windows' and not args.recalcular:
        from evidencia.local_windows import Offline
        consultar = Offline()
    casos = leer_casos(args.lote)
    revision = leer_revision(resultados / f'{args.lote}_revision.tsv')
    metricas = {}
    for version in versiones:
        destino = resultados / f'{args.lote}_{version}.jsonl'
        if not args.recalcular:
            ejecutar(version, casos, destino, consultar, args.backend)
        metricas[version] = medir(leer_salidas(destino), revision)
    sufijo = '' if args.version == 'todas' else f'_{args.version}'
    ruta = resultados / f'{args.lote}_metricas{sufijo}.json'
    ruta.write_text(json.dumps(metricas, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(metricas, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
