"""Clasifica cada pregunta por separado y conserva los datos de la solicitud."""

import json

from v2 import Chatbot as ChatbotV2, INSTRUCCIONES, iniciar


INSTRUCCIONES_TURNO = INSTRUCCIONES + '''

Clasifica exclusivamente mensaje_actual. La solicitud previa solo sirve para resolver cambios
o datos que el cliente aporta ahora. Si la persona pregunta por un precio, la dirección o el
horario comercial, contesta esa pregunta aunque tenga una solicitud. Una consulta sobre el
horario de atención es horario. Preguntar cuánto cuesta es precio, y preguntar cómo llegar
es ubicacion. Usa otra para texto ininteligible, saludos o preguntas ajenas al local. En esos
casos devuelve servicio, dia y hora con null y hora_ambigua false. Una expresión como
«a la misma hora» conserva la hora anterior y tiene hora_ambigua false. Si recibes una aclaración
de mañana o tarde, usa mensaje_hora_pendiente para recuperar el número de hora.'''


class Chatbot(ChatbotV2):
    def __init__(self, consultar=None):
        super().__init__(consultar)
        self.mensaje_hora_pendiente = None

    def preparar_mensajes(self, mensaje):
        contexto = {'mensaje_actual': mensaje}
        if self.solicitud_en_curso:
            contexto['solicitud_en_curso'] = self.estado
            if self.mensaje_hora_pendiente is not None:
                contexto['mensaje_hora_pendiente'] = self.mensaje_hora_pendiente
        return [
            {'role': 'system', 'content': INSTRUCCIONES_TURNO},
            {'role': 'user', 'content': json.dumps(contexto, ensure_ascii=False)},
        ]

    def interpretar(self, mensaje):
        turno = super().interpretar(mensaje)
        if turno['intencion'] == 'solicitud':
            if turno['hora'] is not None:
                self.mensaje_hora_pendiente = None
            elif turno.get('hora_ambigua') is True and self.mensaje_hora_pendiente is None:
                self.mensaje_hora_pendiente = mensaje
        return turno

    def responder_otra(self, turno):
        if turno['hora'] or turno.get('hora_ambigua') is True:
            return super().responder_otra(turno)
        return ('¿Puedes reformular tu pregunta? Puedo ayudarte con precios, horarios, '
                'ubicación o una solicitud de hora.')


if __name__ == '__main__':
    iniciar(Chatbot, __doc__)
