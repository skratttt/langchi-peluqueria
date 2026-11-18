# Peluquería Barrio Sur

Asistente de consola en Python para una peluquería ficticia de Ñuñoa. Responde consultas de precio, horario y ubicación. Reúne servicio, día y hora para resumir una solicitud. La disponibilidad queda por confirmar por el local.

## Iniciar la demo

Usa Python 3.10 o posterior y [Ollama](https://ollama.com/download). Si Ollama no está abierto, inicia `ollama serve` en otra terminal. Desde la raíz del proyecto, ejecuta:

```sh
ollama pull qwen2.5:7b-instruct
python v2.py
```

Escribe estos tres mensajes, uno por turno. La ficha y las salidas de la evaluación están incluidas en el repositorio.

```text
Anótenme la solicitud de corte para el jueves a las 16:15.
¿Podría ser 17:45 en vez de eso?
/salir
```

En la corrida de referencia se usó el GGUF Q4_K_M de Qwen2.5 7B Instruct que ya estaba instalado. Python envía los mensajes a la API local de Ollama para la demo habitual. [Modelo](https://ollama.com/library/qwen2.5:7b-instruct) · [API de chat](https://docs.ollama.com/api/chat)

## Qué hace cada versión

| Versión | Cómo detecta la intención | Cómo trata los datos |
| --- | --- | --- |
| V0 cruda, `v0.py` | Busca literalmente cuatro cadenas predefinidas | Revisa el mensaje actual y devuelve datos solo si logra reunir los tres campos |
| V1 por reglas, `v1.py` | Normaliza mayúsculas y tildes y busca patrones agrupados por intención | Hereda extracción y respuestas de V0 |
| V2, `v2.py` | Qwen devuelve intención y campos del turno en JSON | Python valida los valores, conserva campos anteriores y aplica los cambios. Las respuestas salen de la ficha y del estado |

El [prompt](evidencia/prompt_v0.txt), la [salida íntegra](evidencia/salida_v0.md) y el [bloque extraído](v0.py) pertenecen al primer intento de Qwen. El código trae un método HTTP con un endpoint incorrecto y carece de llamadas a ese método. Su historial se inicializa pero nunca se alimenta. La V0 se pudo ejecutar tal como salió porque solo usó reglas locales. El commit `60836c9` conserva esa versión.

### Del mensaje a la respuesta

En V0 y V1, `responder` dirige el mensaje a un método por intención. Los métodos informativos devuelven texto fijo. El método de solicitud busca servicio y día por coincidencia literal y prueba un formato de hora. V1 solo reemplaza `detectar_intencion`, de modo que cualquier cambio en esa métrica se explica por las reglas del clasificador.

En V2, `interpretar` envía el turno, el estado de la solicitud y los últimos mensajes del cliente al modelo local. Recibe un JSON de campos y filtra valores que no correspondan a los servicios, los días o el formato de hora. `responder_solicitud` integra los cambios. En la demo, el segundo mensaje actualiza `hora` y conserva `servicio` y `dia`. Si la hora se expresa como «a las 5» sin indicar mañana o tarde, la regla de ambigüedad pide precisión.

La consola imprime solo el texto para el cliente. El evaluador recoge además la intención y el estado. La V2 mantiene una solicitud por sesión y usa días de la semana. `ficha.json` contiene los valores que usa para redactar precios, horarios y dirección.

## Repetir la evaluación

```sh
python evaluar.py --lote desarrollo
python evaluar.py --lote final
python evaluar.py --lote final --recalcular
```

Los conjuntos de desarrollo y evaluación suman 10 y 50 conversaciones, respectivamente. `evaluar.py` crea una instancia del chatbot por conversación, alimenta solo los mensajes del cliente y almacena cada respuesta, los campos extraídos, el tiempo y las llamadas al modelo. Conserva el criterio esperado en los archivos de resultados. Estos criterios nunca entran al modelo. Las tres versiones reciben los mismos turnos y la misma ficha del negocio.

La corrida incluida se ejecutó en Windows con `libllama` de Ollama 0.40.16 y una RTX 3070. Esa ruta usa los pesos locales, greedy (temperatura 0), contexto de 8.192 tokens y un máximo de 256 tokens de salida por consulta. El adaptador incluye una gramática JSON y está fijado al binario usado. Para repetir esa ruta con la misma instalación, agrega `--backend libllama-windows` al comando de evaluación o de demo. La configuración habitual usa HTTP local y puede generar variaciones según la versión de Ollama o el hardware.

El archivo `resultados/final_revision.tsv` contiene la revisión de afirmaciones por turno de la corrida incluida. Si una nueva corrida genera una respuesta distinta, el evaluador la deja pendiente de revisión. Los datos se comparan como pares campo–valor, ignorando tildes y mayúsculas. Un valor incorrecto cuenta como un valor esperado faltante y como un par incorrecto o adicional.

## Resultados

| Medida | V0 cruda | V1 por reglas | V2 local |
| --- | ---: | ---: | ---: |
| Conversaciones con respuesta en todos los turnos | 50/50 | 50/50 | 50/50 |
| Intenciones correctas | 12/73 (16,4 %) | 41/73 (56,2 %) | 69/73 (94,5 %) |
| Pares campo–valor recuperados | 0/126 (0 %) | 0/126 (0 %) | 121/126 (96,0 %) |
| Pares incorrectos o adicionales | 0 | 0 | 1 |
| Correcciones con estado final correcto | 0/7 (0 %) | 0/7 (0 %) | 3/7 (42,9 %) |
| Respuestas con afirmaciones sin respaldo | 0/73 (0 %) | 0/73 (0 %) | 1/73 (1,4 %) |

V0 y V1 emitieron respuestas genéricas en 67 y 38 turnos, respectivamente. Estas respuestas cuentan como atendidas para comprobar que el bot siguió ejecutándose. La métrica de intenciones y la recuperación de datos capturan qué entendió cada versión.

V2 perdió una hora que el cliente quería mantener en F34, F36 y F40. En F38 interpretó «las tres y cuarto de la tarde» como 15:45. Ese resumen cuenta como una afirmación sin respaldo. La ejecución tardó una mediana de 3,04 segundos por turno de V2 en el equipo de referencia, con el modelo ya cargado.

La V1 aísla el cambio del clasificador frente a V0. La comparación con V2 mide en conjunto el paso a extracción por modelo, memoria explícita y respuesta construida desde la ficha. La revisión contenida en el paquete la realizó Codex al contrastar las salidas con la ficha y el diálogo.

## Entrega y defensa

El repositorio reúne código, ficha, entrada y salida de la V0, casos anotados y evaluación. La [presentación](presentacion/Defensa_LangChi.pptx) incluye notas para una defensa de 15 minutos. El historial se conserva en `LangChi_Peluqueria.bundle` dentro del paquete. Para recuperarlo en otro computador, ejecuta `git clone LangChi_Peluqueria.bundle LangChi_Peluqueria_Git` desde la carpeta que contiene el bundle.
