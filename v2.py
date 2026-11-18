"""Qwen interpreta el turno. Python conserva los campos y redacta la respuesta."""

import argparse
import json
from pathlib import Path
import re

from comun import CAMPOS, INTENCIONES, consola, consultar_ollama, normalizar


FICHA = json.loads(Path(__file__).with_name('ficha.json').read_text(encoding='utf-8'))
DIAS = {normalizar(dia): dia for dia in FICHA['horarios']}
HORA = re.compile(r'(?:[01]\d|2[0-3]):[0-5]\d')
HORA_SIN_PERIODO = re.compile(
    r'\b(?:a las?|tipo)\s+(?:0?[1-9]|1[0-2])\b'
    r'(?!\s*(?:[:h]|\.\d|[ap]\.?\s*m\b|de la (?:manana|tarde|noche)|y\s|menos\s))'
)
INSTRUCCIONES = '''Clasifica el mensaje actual de un cliente de una peluquería chilena y extrae datos.
Devuelve únicamente un objeto JSON con claves intencion, servicio, dia, hora, hora_ambigua.
intencion: precio, horario (horas de funcionamiento), ubicacion, solicitud (pedir o modificar una hora), u otra.
Una pregunta de precio, horario o ubicación sigue siendo informativa aunque haya una solicitud en curso.
Una pregunta de disponibilidad para un servicio, día u hora se interpreta como solicitud. Una hora aislada
sin solicitud en curso ni señal de que quiere agendar es otra. Una corrección o un dato que completa
la solicitud en curso es solicitud. Si pide información ajena al local, usa otra.
servicio: corte (incluye cortarse el pelo y diminutivos), barba o color (incluye teñirse), o null.
dia: día de la semana en español o null. Si la consulta informativa abarca varios días devuelve null.
hora: HH:MM (24 horas) o null. Mediodía es 12:00. Una hora sin minutos entre 1 y 12 sin indicación
de mañana/tarde es ambigua: devuelve hora null y hora_ambigua true. No resuelvas la ambigüedad
a partir del horario comercial. Las horas ya escritas como HH:MM son explícitas. Si antes dio
un número de hora ambiguo y ahora aclara mañana o tarde, combínalos usando el historial.
hora_ambigua: true si el turno actual propone una hora ambigua, de lo contrario false.
Completa solo los campos que aporta o modifica el mensaje actual. Si dice «a la misma hora» no
repitas la hora previa: el valor queda null y Python conserva el campo. Ante preguntas de precio
o de horario, servicio y día pueden especificar la consulta. Nunca inventes un campo.'''


class Chatbot:
    def __init__(self, consultar=None):
        self.consultar = consultar or consultar_ollama
        self.estado = dict.fromkeys(CAMPOS)
        self.historial = []
        self.solicitud_en_curso = False
        self.hora_ambigua = False

    def preparar_mensajes(self, mensaje):
        contexto = {
            'solicitud_en_curso': self.solicitud_en_curso,
            'estado': self.estado,
            'hay_hora_pendiente_de_aclarar': self.hora_ambigua,
            'mensajes_previos_del_cliente': self.historial[-5:],
            'mensaje_actual': mensaje,
        }
        return [
            {'role': 'system', 'content': INSTRUCCIONES},
            {'role': 'user', 'content': json.dumps(contexto, ensure_ascii=False)},
        ]

    def interpretar(self, mensaje):
        turno = json.loads(self.consultar(self.preparar_mensajes(mensaje), json_mode=True))
        if not isinstance(turno, dict) or turno.get('intencion') not in INTENCIONES:
            raise ValueError('El modelo devolvió una intención inválida.')
        servicio = normalizar(turno.get('servicio'))
        hora = str(turno.get('hora') or '')
        turno['servicio'] = servicio if servicio in FICHA['servicios'] else None
        turno['dia'] = DIAS.get(normalizar(turno.get('dia')))
        turno['hora'] = hora if HORA.fullmatch(hora) else None
        if HORA_SIN_PERIODO.search(normalizar(mensaje) or ''):
            turno['hora'] = None
            turno['hora_ambigua'] = True
        return turno

    def responder(self, mensaje):
        turno = self.interpretar(mensaje)
        intencion = turno['intencion']
        if intencion == 'solicitud':
            respuesta = self.responder_solicitud(turno)
        elif intencion == 'precio':
            respuesta = responder_precio(mensaje, turno['servicio'])
        elif intencion == 'horario':
            respuesta = responder_horario(turno['dia'])
        elif intencion == 'ubicacion':
            respuesta = f"Estamos en {FICHA['direccion']}."
        else:
            respuesta = self.responder_otra(turno)
        self.historial.append(mensaje)
        return {'intencion': intencion, 'datos': self.estado.copy(), 'respuesta': respuesta}

    def responder_otra(self, turno):
        if turno['hora'] or turno.get('hora_ambigua') is True:
            return '¿Quieres consultar el horario de atención o pedir una hora para un servicio?'
        servicios = ', '.join(FICHA['servicios'])
        return (f'Por ahora tengo información sobre {servicios}, sus precios, el horario y la dirección. '
                'También puedo ayudarte a preparar una solicitud de hora.')

    def responder_solicitud(self, turno):
        self.solicitud_en_curso = True
        self.estado.update({campo: turno[campo] for campo in CAMPOS if turno[campo] is not None})
        if turno['hora']:
            self.hora_ambigua = False
        elif turno.get('hora_ambigua') is True:
            self.hora_ambigua = True
            self.estado['hora'] = None

        if self.hora_ambigua:
            return '¿Te refieres a esa hora de la mañana o de la tarde?'
        etiquetas = {'servicio': 'el servicio (corte, barba o color)', 'dia': 'el día', 'hora': 'la hora'}
        faltantes = [etiquetas[campo] for campo in CAMPOS if self.estado[campo] is None]
        if faltantes:
            detalle = ', '.join(faltantes[:-1]) + ' y ' + faltantes[-1] if len(faltantes) > 1 else faltantes[0]
            return f'Para resumir la solicitud, indícame {detalle}, por favor.'

        servicio, dia, hora = (self.estado[campo] for campo in CAMPOS)
        resumen = f'Solicitud: {servicio} el {dia} a las {hora}.'
        horario = FICHA['horarios'][dia]
        if horario == 'cerrado':
            return f'{resumen} Ese día el local está cerrado. ¿Qué otro día te acomoda?'
        apertura, cierre = horario.split('–')
        if not apertura <= hora < cierre:
            return f'{resumen} Ese día atendemos entre {apertura} y {cierre}. ¿Qué otra hora te acomoda?'
        return f'{resumen} La disponibilidad queda por confirmar.'


def responder_precio(mensaje, servicio):
    texto = normalizar(mensaje) or ''
    servicios = [nombre for nombre in FICHA['servicios'] if re.search(rf'\b{nombre}\b', texto)]
    if servicio and servicio not in servicios:
        servicios.append(servicio)
    precios = [f"{nombre}: ${FICHA['servicios'][nombre]:,}".replace(',', '.')
               for nombre in servicios or FICHA['servicios']]
    return ' · '.join(precios) + ' CLP.'


def responder_horario(dia):
    horarios = FICHA['horarios']
    if dia:
        horario = horarios[dia]
        if horario == 'cerrado':
            return f'El {dia} está cerrado.'
        return f"El {dia} atendemos de {horario.replace('–', ' a ')}."
    semanal = horarios['lunes'].replace('–', ' a ')
    sabado = horarios['sábado'].replace('–', ' a ')
    return f'Lunes a viernes de {semanal}, sábado de {sabado} y domingo cerrado.'


def iniciar(clase, descripcion):
    parser = argparse.ArgumentParser(description=descripcion)
    parser.add_argument('--backend', choices=('ollama', 'libllama-windows'), default='ollama')
    args = parser.parse_args()
    consultar = consultar_ollama
    if args.backend == 'libllama-windows':
        from evidencia.local_windows import Offline
        consultar = Offline()
    consola(clase(consultar))


if __name__ == '__main__':
    iniciar(Chatbot, __doc__)
