# Peluquería Barrio Sur

Asistente de consola en Python para una peluquería ficticia de Ñuñoa. Responde consultas de precio, horario y ubicación. Reúne servicio, día y hora para resumir una solicitud. La disponibilidad queda por confirmar por el local.

## Iniciar la demo

Usa Python 3.10 o posterior y [Ollama](https://ollama.com/download). Si Ollama no está abierto, inicia `ollama serve` en otra terminal. Desde la raíz del proyecto, ejecuta:

```sh
ollama pull qwen2.5:7b-instruct
python v3.py
```

Escribe estos tres mensajes, uno por turno. La ficha y las salidas de la evaluación están incluidas en el repositorio.

```text
Anótenme la solicitud de corte para el jueves a las 16:15.
¿Podría ser 17:45 en vez de eso?
/salir
```

En la corrida de referencia se usó el GGUF Q4_K_M de Qwen2.5 7B Instruct que ya estaba instalado. Python envía los mensajes a la API local de Ollama para la demo habitual. [Modelo](https://ollama.com/library/qwen2.5:7b-instruct) · [API de chat](https://docs.ollama.com/api/chat)

La demo usa V3. Qwen recibe la pregunta actual y los datos pertinentes de la solicitud en curso. Eso permite cambiar de tema y retomar una solicitud sin reenviar las consultas informativas anteriores. La tabla y la presentación incluyen la evaluación de las cuatro versiones.

## Qué hace cada versión

| Versión | Cómo detecta la intención | Cómo trata los datos |
| --- | --- | --- |
| V0 cruda, `v0.py` | Busca literalmente cuatro cadenas predefinidas | Revisa el mensaje actual y devuelve datos solo si logra reunir los tres campos |
| V1 por reglas, `v1.py` | Normaliza mayúsculas y tildes y busca patrones agrupados por intención | Hereda extracción y respuestas de V0 |
| V2, `v2.py` | Qwen devuelve intención y campos del turno en JSON | Python valida los valores, conserva campos anteriores y aplica los cambios. Las respuestas salen de la ficha y del estado |
| V3, `v3.py` | Qwen recibe el mensaje actual sin las consultas informativas anteriores | Conserva el estado de la solicitud y el mensaje de una hora pendiente de aclaración |

### Evidencia de la primera versión

El commit [`60836c9`](https://github.com/skratttt/langchi-peluqueria/commit/60836c98b91056e356a094a725752ec7df8356dd) conserva el primer intento de Qwen2.5 7B Instruct. El modelo se ejecutó localmente para generar el código.

| Evidencia | Qué contiene |
| --- | --- |
| [Prompt exacto](evidencia/prompt_v0.txt) | El encargo enviado al modelo, con la ficha, las cinco intenciones, la interfaz de Python y la petición de usar el modelo y conservar datos entre turnos. |
| [Respuesta íntegra de Qwen](evidencia/salida_v0.md) | La introducción, el bloque de código y las instrucciones de ejecución que devolvió el modelo. |
| [Código crudo](v0.py) | El bloque Python de esa respuesta, extraído sin editar. Es el punto de partida de la comparación. |
| [Pruebas de V0](resultados/final_v0.jsonl) | Las respuestas observadas, con el resultado esperado y los datos recuperados de cada turno. |

La respuesta original decía que el bot mantendría en cuenta el historial. El código crea la lista, pero nunca agrega los turnos. También declara un método HTTP con una ruta incorrecta y nunca lo llama. La V0 funcionó con coincidencias literales. En F01, «¿Cuánto cobran por un corte de pelo?» era una consulta de precio que V0 clasificó como «otra» porque buscaba la palabra «precio». En la evaluación final acertó 12 de 73 intenciones y recuperó 0 de 126 pares campo-valor.

### Del mensaje a la respuesta

En V0 y V1, `responder` dirige el mensaje a un método por intención. Los métodos informativos devuelven texto fijo. El método de solicitud busca servicio y día por coincidencia literal y prueba un formato de hora. V1 solo reemplaza `detectar_intencion`, de modo que cualquier cambio en esa métrica se explica por las reglas del clasificador.

En V2, `interpretar` envía el turno, el estado de la solicitud y los últimos mensajes del cliente al modelo local. Recibe un JSON de campos y filtra valores que no correspondan a los servicios, los días o el formato de hora. `responder_solicitud` integra los cambios. En la demo, el segundo mensaje actualiza `hora` y conserva `servicio` y `dia`. Si la hora se expresa como «a las 5» sin indicar mañana o tarde, la regla de ambigüedad pide precisión.

En V3, `preparar_mensajes` conserva el mensaje actual, los campos de la solicitud y, cuando corresponde, la frase que contiene una hora pendiente de aclaración. `responder_otra` ofrece una reformulación ante entradas ininteligibles o consultas fuera del alcance.

| Componente | Función |
| --- | --- |
| `comun.py` | `consultar_ollama` llama a la API local con temperatura cero. `normalizar` unifica tildes y mayúsculas para buscar palabras o comparar valores. `consola` recibe los turnos e imprime la respuesta. |
| `ficha.json` | Define los servicios, precios, horarios y dirección del local ficticio. Python consulta esta ficha para redactar las respuestas de V2 y V3. |
| `evaluar.py` | `leer_casos` agrupa los turnos por conversación. `ejecutar` crea una instancia por conversación y guarda las salidas. `medir` compara intención y datos con lo esperado y usa la revisión de afirmaciones ligada a la huella de cada respuesta. |
| `evidencia/local_windows.py` | Permite reproducir la evaluación en la instalación Windows registrada, ejecutando los mismos pesos en el proceso de Python con `libllama`. La demo habitual usa Ollama. |

V2 y V3 mantienen una solicitud por sesión, usan días de la semana y resumen lo pedido. La disponibilidad queda a cargo del local.

## Repetir la evaluación

```sh
python evaluar.py --lote desarrollo
python evaluar.py --lote final
python evaluar.py --lote final --recalcular
```

Los conjuntos de desarrollo y evaluación contienen 10 y 50 conversaciones, respectivamente. `evaluar.py` crea una instancia del chatbot por conversación, alimenta los mensajes del cliente y almacena cada respuesta, los campos extraídos, el tiempo y las llamadas al modelo. Conserva el criterio esperado en los archivos de resultados. Los criterios se usan para calificar las salidas. Las cuatro versiones reciben los mismos turnos y trabajan con los mismos datos del negocio.

La corrida incluida se ejecutó en Windows con `libllama` de Ollama 0.40.16 y una RTX 3070. Esa ruta usa los pesos locales, greedy (temperatura 0), contexto de 8.192 tokens y un máximo de 256 tokens de salida por consulta. El adaptador incluye una gramática JSON y está fijado al binario usado. Para repetir esa ruta con la misma instalación, agrega `--backend libllama-windows` al comando de evaluación o de demo. La configuración habitual usa HTTP local y puede generar variaciones según la versión de Ollama o el hardware.

El archivo `resultados/final_revision.tsv` contiene la revisión de afirmaciones por turno de la corrida incluida. Si una nueva corrida genera una respuesta distinta, el evaluador la deja pendiente de revisión. Los datos se comparan como pares campo–valor, ignorando tildes y mayúsculas. Un valor incorrecto cuenta como un valor esperado faltante y como un par incorrecto o adicional.

## Resultados

| Medida | V0 cruda | V1 por reglas | V2 local | V3 local |
| --- | ---: | ---: | ---: | ---: |
| Conversaciones con respuesta en todos los turnos | 50/50 | 50/50 | 50/50 | 50/50 |
| Intenciones correctas | 12/73 (16,4 %) | 41/73 (56,2 %) | 69/73 (94,5 %) | 70/73 (95,9 %) |
| Pares campo-valor recuperados | 0/126 (0 %) | 0/126 (0 %) | 121/126 (96,0 %) | 119/126 (94,4 %) |
| Pares incorrectos o adicionales | 0 | 0 | 1 | 4 |
| Correcciones con estado final correcto | 0/7 (0 %) | 0/7 (0 %) | 3/7 (42,9 %) | 4/7 (57,1 %) |
| Respuestas con afirmaciones sin respaldo | 0/73 (0 %) | 0/73 (0 %) | 1/73 (1,4 %) | 1/73 (1,4 %) |

V0 y V1 emitieron respuestas genéricas en 67 y 38 turnos, respectivamente. Estas respuestas cuentan como atendidas para comprobar que el bot siguió ejecutándose. La métrica de intenciones y la recuperación de datos capturan qué entendió cada versión.

V3 acertó una intención y una corrección final más que V2 y recuperó dos pares esperados menos. En F29 pidió aclarar una hora que el cliente ya había dado como 17:30. En F38, ambas versiones interpretaron «las tres y cuarto de la tarde» como 15:45. Cada resumen con esa hora cuenta como una afirmación sin respaldo. En desarrollo, V3 devolvió una etiqueta fuera del conjunto de intenciones en D05. El evaluador conservó el error y la consola pide reformular ante ese tipo de salida.

V1 funciona como alternativa simplificada por reglas frente a V2 y V3. El contraste V0–V1 aísla el cambio del clasificador. El salto a V2 mide conjuntamente el uso del modelo para interpretar, la memoria explícita y la construcción de respuestas desde la ficha. La revisión de afirmaciones incluida la realizó Codex al contrastar las salidas con la ficha y el diálogo.

## Entrega y defensa

La [presentación](presentacion/Defensa_LangChi.pptx) incluye nueve láminas con notas para una defensa de 15 minutos. Las láminas 3 a 5 muestran el prompt, la salida y el diagnóstico de V0. Los anexos A y B contienen el prompt completo y la respuesta del modelo, incluido el código crudo. Para preparar la demostración, revisa el caso F35 de la lámina 8. El historial también se conserva en `LangChi_Peluqueria.bundle` dentro del paquete descargable del proyecto.

El enunciado fija la entrega en GitHub para el martes 24 de noviembre de 2026 a las 23:59. Tras recuperar el repositorio, sitúate en `LangChi_Peluqueria_Git`. Con una sesión válida de GitHub CLI puedes crear un repositorio privado y subir su historial con `gh repo create langchi-peluqueria --private --source . --remote github --push`. Selecciona las cuentas del profesor y la ayudante para habilitar su acceso. La presentación se coordina con el profesor para la semana del 23 de noviembre. El curso pide equipos de tres o cuatro personas, con autorización del profesor para tamaños distintos. [GitHub CLI](https://cli.github.com/manual/gh_repo_create)
