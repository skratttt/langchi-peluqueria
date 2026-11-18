import json
import urllib.request
from datetime import datetime

class Chatbot:
    def __init__(self, consultar=None):
        self.historial = []
        self.consultar = consultar or self.http_request

    def detectar_intencion(self, mensaje):
        if "precio" in mensaje:
            return "precio"
        elif "horario" in mensaje:
            return "horario"
        elif "ubicacion" in mensaje:
            return "ubicacion"
        elif "solicitud" in mensaje:
            return "solicitud"
        else:
            return "otra"

    def responder(self, mensaje):
        intencion = self.detectar_intencion(mensaje)
        if intencion == "precio":
            return self.responder_precio()
        elif intencion == "horario":
            return self.responder_horario()
        elif intencion == "ubicacion":
            return self.responder_ubicacion()
        elif intencion == "solicitud":
            return self.responder_solicitud(mensaje)
        else:
            return {"intencion": intencion, "datos": {}, "respuesta": "No entendí tu consulta. Por favor, proporciona más detalles."}

    def responder_precio(self):
        return {"intencion": "precio", "datos": {}, "respuesta": "Los servicios disponibles son:\n- Corte: $12.000 CLP\n- Barba: $8.000 CLP\n- Color: $30.000 CLP"}

    def responder_horario(self):
        return {"intencion": "horario", "datos": {}, "respuesta": "Estamos abiertos de lunes a viernes de 10:00 a 19:00 y el sábado de 10:00 a 16:00. Cerrado el domingo."}

    def responder_ubicacion(self):
        return {"intencion": "ubicacion", "datos": {}, "respuesta": "Nuestra dirección es Avenida Los Telares 184, Ñuñoa, Santiago."}

    def responder_solicitud(self, mensaje):
        servicio = None
        dia = None
        hora = None
        datos = {}

        if "corte" in mensaje:
            servicio = "Corte"
        elif "barba" in mensaje:
            servicio = "Barba"
        elif "color" in mensaje:
            servicio = "Color"

        if "lunes" in mensaje:
            dia = "lunes"
        elif "martes" in mensaje:
            dia = "martes"
        elif "miércoles" in mensaje:
            dia = "miércoles"
        elif "jueves" in mensaje:
            dia = "jueves"
        elif "viernes" in mensaje:
            dia = "viernes"
        elif "sábado" in mensaje:
            dia = "sábado"

        if dia and "hora" in mensaje:
            try:
                hora = datetime.strptime(mensaje.split("hora")[1].strip(), "%H:%M")
                hora = hora.strftime("%H:%M")
            except ValueError:
                pass

        if servicio and dia and hora:
            return {"intencion": "solicitud", "datos": {"servicio": servicio, "dia": dia, "hora": hora}, "respuesta": f"Tu solicitud para {servicio} el {dia} a las {hora} ha sido recibida. Estaremos en contacto con más detalles."}
        else:
            return {"intencion": "solicitud", "datos": {}, "respuesta": "Por favor, proporciona más detalles para confirmar tu solicitud."}

    def http_request(self, mensajes, json_mode=True):
        url = "http://localhost:8000/api/v1/ollama"
        data = json.dumps({"messages": mensajes}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req) as response:
            return response.read().decode("utf-8")

if __name__ == "__main__":
    chatbot = Chatbot()
    while True:
        mensaje = input("Tú: ")
        respuesta = chatbot.responder(mensaje)
        print("Chatbot:", respuesta["respuesta"])
