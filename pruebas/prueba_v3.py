import json
import unittest

from v3 import Chatbot


class PruebaCambioDeTema(unittest.TestCase):
    def test_mensaje_desconocido_despues_de_ubicacion(self):
        def consultar(mensajes, *, json_mode):
            contexto = json.loads(mensajes[-1]['content'])
            self.assertEqual(set(contexto), {'mensaje_actual'})
            intencion = 'ubicacion' if 'peluquería' in contexto['mensaje_actual'] else 'otra'
            return json.dumps({'intencion': intencion})

        bot = Chatbot(consultar)
        self.assertEqual(bot.responder('¿Dónde queda la peluquería?')['intencion'], 'ubicacion')
        respuesta = bot.responder('asdasdaw')
        self.assertEqual(respuesta['intencion'], 'otra')
        self.assertIn('reformular', respuesta['respuesta'])

    def test_consulta_informativa_entre_solicitud_y_correccion(self):
        def consultar(mensajes, *, json_mode):
            contexto = json.loads(mensajes[-1]['content'])
            mensaje = contexto['mensaje_actual']
            if mensaje.startswith('Corte'):
                return json.dumps({'intencion': 'solicitud', 'servicio': 'corte',
                                   'dia': 'jueves', 'hora': '16:15'})
            self.assertEqual(contexto['solicitud_en_curso']['hora'], '16:15')
            self.assertNotIn('mensajes_previos_del_cliente', contexto)
            if 'dirección' in mensaje:
                return json.dumps({'intencion': 'ubicacion'})
            return json.dumps({'intencion': 'solicitud', 'hora': '17:45'})

        bot = Chatbot(consultar)
        bot.responder('Corte el jueves a las 16:15')
        self.assertEqual(bot.responder('¿Cuál es la dirección?')['intencion'], 'ubicacion')
        datos = bot.responder('Mejor a las 17:45')['datos']
        self.assertEqual(datos, {'servicio': 'corte', 'dia': 'jueves', 'hora': '17:45'})


if __name__ == '__main__':
    unittest.main()
