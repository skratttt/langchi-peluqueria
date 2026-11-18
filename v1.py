"""Variante por reglas. Reutiliza la extracción y las respuestas de V0."""

import re

from comun import consola, normalizar
from v0 import Chatbot as ChatbotBase


PATRONES = {
    'precio': r'precio|cuanto|vale|cobran|valores|a cuanto sale',
    'horario': r'horario|atienden|abren|cierran|hasta que hora|desde que hora',
    'ubicacion': r'ubicacion|direccion|donde|comuna|calle',
    'solicitud': r'solicitud|solicito|solicitar|pedir hora|pedir una hora|quiero hora|agendar|reservar|cita|anot[ae]\w*',
}


class Chatbot(ChatbotBase):
    def detectar_intencion(self, mensaje):
        texto = normalizar(mensaje) or ''
        for intencion, expresiones in PATRONES.items():
            if re.search(rf'\b(?:{expresiones})\b', texto):
                return intencion
        return 'otra'


if __name__ == '__main__':
    consola(Chatbot())
