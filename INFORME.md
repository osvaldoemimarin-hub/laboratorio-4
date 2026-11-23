# Informe — Laboratorio 4: LLMOps con un RAG local sobre documentos de INCIVA

**Autor:** Osvaldo Marín Mora; Edgar Adrian Ortiz; Nilson Jacobo Gonzales; Juan Andrés Ruiz · Maestría en IA y Ciencia de Datos (UAO) · Gestión de Proyectos de IA
**Fecha de ejecución:** 22 de noviembre de 2026
**Caso:** asistente documental sobre el convenio interadministrativo de educación ambiental 2017
(Gobernación del Valle – Secretaría de Educación / INCIVA), tomado del corpus de mi trabajo de grado.

Todas las cifras de este informe vienen de corridas reales guardadas en `resultados/` y `evidencias/`.
Entorno: Windows 11, Docker Desktop (motor WSL2), Ollama en contenedor **solo CPU**, `qwen2.5:1.5b`
para generar y `nomic-embed-text` para embeddings.

---

## 1. Arquitectura de los cinco servicios (Docker Compose)

`docker-compose.yml` levanta `ollama`, `mlflow`, `api`, `prometheus` y `grafana`, todos publicados solo
en `127.0.0.1`. Estado verificado (`evidencias/docker_compose_ps.txt`):

```
NAME         IMAGE                    STATUS          PORTS
grafana      grafana/grafana:latest   Up 21 minutes   127.0.0.1:3000->3000/tcp
llmops-api   laboratorio_4-api        Up 21 minutes   127.0.0.1:8000->8000/tcp
mlflow       laboratorio_4-mlflow     Up 21 minutes   127.0.0.1:5000->5000/tcp
ollama       ollama/ollama:latest     Up 21 minutes   127.0.0.1:11435->11434/tcp
prometheus   prom/prometheus:latest   Up 21 minutes   127.0.0.1:9090->9090/tcp
```

`GET /health` → `{"estado":"ok"}`. Captura de Swagger: `evidencias/capturas/01_fastapi_swagger.png`.

Única diferencia de red con la guía: Ollama se publica en el puerto **11435** del host porque el
11434 lo usa el Ollama nativo de la tesis. Dentro de la red de Compose la API sigue usando
`http://ollama:11434`.

## 2. Ollama ejecutando el modelo local

`evidencias/ollama_list.txt`: `qwen2.5:1.5b` (986 MB) y `nomic-embed-text` (274 MB).

Misma pregunta dos veces por `/api/generate` (`evidencias/ollama_tokens_frio_caliente.txt`):

| Ejecución | prompt_eval_count | eval_count | load_duration | total_duration | tokens/s |
|---|---|---|---|---|---|
| 1ª (arranque en frío) | 37 | 80 | **1,543 s** | 4,22 s | 33,0 |
| 2ª (modelo en memoria) | 37 | 70 | **0,0015 s** | 2,09 s | 34,2 |

**Actividad del paso 12:** `load_duration` sí cambia: pasa de 1,5 s a 1,5 ms. El arranque en frío
duplica la duración total, aunque la velocidad de generación (~33–34 tok/s en CPU) no cambia.
De paso se vio que el modelo base no conoce el término "LLMOps" y lo reconoce, en vez de inventar.

## 3. Archivos documentales e indexación RAG

`scripts/preparar_corpus.py` genera 6 `.txt` a partir del texto que la tesis ya había extraído
(capa nativa u OCR) y aplica su anonimizador (cédulas, vecindad, lugar de expedición). Además
enmascara correos y una cédula que el OCR había partido en dos líneas.

| Documento | Caracteres |
|---|---|
| convenio_2017.txt | 45 787 |
| acta_inicio_convenio_2017.txt | 3 316 |
| estudios_previos_2017.txt | 40 427 |
| matriz_riesgo_2017.txt | 7 209 |
| informe_actividades_2017.txt | 74 630 |
| informe_supervision_2017.txt | 82 425 |

`POST /indexar` (`evidencias/indexacion.json`):
`{"documentos":6,"fragmentos":606,"tamano_fragmento":500,"solape":80,"modelo_embedding":"nomic-embed-text","segundos":60.36}`.
El índice `datos/indice.json` pesa 9,0 MB. No se versiona y se regenera con `/indexar`.

## 4. Una consulta y sus fragmentos recuperados

`evidencias/consulta_ejemplo.json`: *"¿Cuál es el valor del convenio interadministrativo de
educación ambiental de 2017?"*, `top_k=3`, `temperatura=0.2`.

| Fuente | Fragmento | Similitud |
|---|---|---|
| informe_supervision_2017.txt | 147 | 0,756 |
| convenio_2017.txt | 1 | 0,756 |
| informe_actividades_2017.txt | 135 | 0,752 |

Tokens de entrada: 718. Tokens de salida: 273. Recuperación: 0,15 s. Generación: 8,28 s.

**Respuesta:** el modelo entendió "valor" como *importancia* y escribió tres párrafos sobre la
relevancia del convenio. No dio la cifra ($1.368.486.228). Es una respuesta fluida pero **no
responde la pregunta**. La causa se ve en la traza (sección 5).

**Pregunta del paso 20:** la consulta RAG consume 718 tokens de entrada, frente a 37 de una pregunta
directa, porque el prompt lleva las instrucciones, los fragmentos y la pregunta.

## 5. Traza completa en MLflow

Experimento `Laboratorio_RAG_Ollama` con 85 trazas. Capturas: `evidencias/capturas/04_mlflow_trazas.png`
y `06_mlflow_traza_detalle.png`. Árbol de spans (`evidencias/traza_mlflow.txt`):

```
pipeline_rag              11.93 s
├── recuperar_documentos   0.15 s
└── generar_respuesta_llm 11.74 s   (718 tokens entrada, 273 salida)
```

En el span `generar_respuesta_llm` se ve el contexto que recibió el LLM. El primer fragmento
(informe de supervisión, nº 147) habla de **"valores ambientales"**: los embeddings confundieron
"valor" (monto) con "valores" (principios). El fallo nace en la recuperación, no en el LLM.

La traza también registró el único error del laboratorio: `ReadTimeout` de 300 s en
`generar_respuesta_llm` (pregunta N02 con `top_k=1`). El modelo generó sin parar hasta agotar el
tiempo, y la excepción quedó guardada en el span con su *stacktrace*.

## 6. Consultas PromQL: tokens, latencia y similitud

Prometheus marca el objetivo `llmops_api` como **UP** (`evidencias/capturas/02_prometheus_targets.png`).
Valores al final de las pruebas (`evidencias/promql.txt`). Se usó una ventana de 30 min para cubrir
toda la corrida; la guía usa 5 min.

| Indicador | PromQL | Valor |
|---|---|---|
| Consultas exitosas | `llm_consultas_total{estado="exito"}` | 84 |
| Consultas con error | `llm_consultas_total{estado="error"}` | 1 |
| Tokens de entrada | `llm_tokens_entrada_total` | 57 875 |
| Tokens de salida | `llm_tokens_salida_total` | 7 161 |
| Tasa de tokens de salida | `rate(llm_tokens_salida_total[30m])` | 3,99 tok/s (agregado) |
| Latencia media | `rate(llm_duracion_segundos_sum[30m]) / rate(llm_duracion_segundos_count[30m])` | 7,13 s |
| Latencia p95 | `histogram_quantile(0.95, rate(llm_duracion_segundos_bucket[30m]))` | 11,87 s |
| Similitud media | `rate(rag_similitud_sum[30m]) / rate(rag_similitud_count[30m])` | 0,735 |
| Recuperación media | `rate(rag_recuperacion_segundos_sum[30m]) / rate(rag_recuperacion_segundos_count[30m])` | 0,053 s |

La tasa agregada (3,99 tok/s) no es la velocidad del modelo (~33 tok/s). Es el promedio sobre
30 min, que incluye los tiempos muertos y la evaluación del prompt.

## 7. Dashboard de Grafana

El dashboard **"Monitoreo LLMOps: Ollama y RAG"** queda precargado desde
`grafana/provisioning/dashboards/llmops.json`. Tiene los 6 paneles del paso 27 más la latencia p95 y
la tasa de tokens. Captura con datos reales: `evidencias/capturas/05_grafana_dashboard.png`
(85 consultas, 57 875 tokens de entrada, 7 161 de salida).

En la latencia media y la p95 se ve un pico de varios minutos: es el *timeout* de 300 s de la
sección 5. Un solo evento así distorsiona la media, y por eso conviene vigilar también percentiles y
errores.

**Actividad del paso 27:** la consulta exitosa más lenta duró 11,93 s, de los cuales
**11,74 s (98 %) fueron generación** y 0,15 s recuperación. En todas las corridas la recuperación
quedó por debajo de 0,16 s: el costo de tiempo está en el LLM en CPU.

## 8. Comparación de top_k (experimento A)

Doce preguntas tomadas del *gold standard* de la tesis: 9 con respuesta en los documentos y 3 sin
evidencia (F2, F4, F5). Temperatura 0,2. Fuente: `resultados/experimento_A.json` y `resultados/resumen.md`.

| Indicador | K = 1 | K = 3 | K = 5 |
|---|---|---|---|
| Tiempo RAG medio | 0,078 s | 0,050 s | 0,040 s |
| Tokens de entrada medios | 331 | 670 | 1 008 |
| Tokens de salida medios | 27 | 55 | 92 |
| Generación media | 0,72 s | 1,59 s | 2,76 s |
| Duración total media | 3,88 s | 5,73 s | 6,77 s |
| Similitud máxima media | 0,736 | 0,740 | 0,740 |
| **Correctas (revisión manual, de 9)** | **1** | **2** | **2** |
| Incompletas | 0 | 2 | 3 |
| Incorrectas / no fundamentadas | 1 | 2 | 3 |
| Rechazos indebidos ("no existe información") | 6 | 3 | 1 |
| Error (timeout) | 1 | 0 | 0 |
| Rechazos correctos sin evidencia (de 3) | 3 | 3 | 3 |

El tiempo RAG baja al subir K solo porque el modelo de embeddings ya estaba caliente en las corridas
siguientes. Recorrer 606 vectores cuesta lo mismo con cualquier K.

Calificación manual de cada respuesta frente a los documentos:

| id | Pregunta (resumida) | K = 1 | K = 3 | K = 5 |
|---|---|---|---|---|
| G2 | Objeto del convenio | Incorrecta (da la meta de 3.773 niños) | Incompleta (da un componente) | Incorrecta (confunde objeto con componente) |
| N01 | Valor del convenio | Rechazo | Incorrecta ("valor" = importancia) | Incorrecta (idem) |
| N02 | Componentes | Error (timeout) | Incompleta (2 de 3, inventa "sistematizar") | Incompleta (3 correctos mezclados con 4 inventados) |
| N03 | Municipios | **Correcta** | **Correcta** | **Correcta** |
| G4 | Fecha del acta de inicio | Rechazo | **Correcta** (4 jul 2017) | **Correcta** (+ Santiago de Cali) |
| G1 | Supervisor | Rechazo | Incorrecta ("no se especifica") | Incompleta (solo la Secretaría) |
| I1 | Actividades en Buga | Rechazo | Rechazo | Incompleta (genérica, sin las I.E.) |
| N04 | Grados de los vigías | Rechazo | Rechazo | **Inventada** ("niños de 2-3 años de edad") |
| I2 | Conclusión del supervisor | Rechazo | Rechazo | Rechazo |

**Análisis.**
- **Más contexto no garantiza una mejor respuesta.** De K = 3 a K = 5 los tokens de entrada suben
  un 50 % (670 → 1 008) y la generación un 74 % (1,59 → 2,76 s), pero las respuestas correctas
  siguen en 2. Lo que cambia es el tipo de fallo: con K = 1 el modelo se niega (6 rechazos
  indebidos), con K = 5 intenta responder y produce respuestas incompletas o inventadas (N04).
  Cambia un fallo *seguro* (rechazar) por uno *peligroso* (inventar).
- **K = 3 es la configuración que logra respuestas correctas con menos recursos:** las mismas
  2 correctas que K = 5 con un 34 % menos de tokens de entrada, menos tiempo y sin respuestas
  inventadas sobre los grados escolares.
- **La heurística automática engaña.** La columna `contiene_clave` marca 6/9 con K = 5, pero la
  revisión manual encuentra solo 2 correctas. Contener una palabra clave no es estar en lo cierto
  (N02 lista los componentes reales junto con otros inventados).
- **El cuello de botella es la recuperación.** El diagnóstico (`evidencias/diagnostico_recuperacion.txt`)
  muestra que el fragmento con el valor del convenio queda en la **posición 29** (similitud 0,702,
  contra 0,756 del primero). La conclusión del informe de supervisión (I2) queda en la
  **posición 56**. Ningún K razonable las alcanza. Las similitudes están muy apretadas
  (0,65–0,79), así que el coseno apenas distingue entre fragmentos. **Una similitud alta no
  demuestra pertinencia.**

## 9. Temperatura, preguntas sin evidencia y calidad

### Experimento B: temperatura (`resultados/experimento_B.json`)

Tres preguntas, tres repeticiones por temperatura, K = 3:

| Temperatura | Respuestas distintas (de 9) | Tokens de salida medios |
|---|---|---|
| 0,0 | 5 | 56 |
| 0,5 | 9 | 62 |
| 1,0 | 9 | 73 |

- Con **0,0** la redacción varía, pero el dato se mantiene (siempre "4 de julio de 2017"). La
  variación con temperatura 0 viene de que Ollama no fija semilla y procesa en paralelo, así que
  tampoco hay determinismo completo.
- Con **1,0** las respuestas se alargan y aparece la **alucinación**: en una de tres repeticiones el
  acta de inicio pasa a estar firmada el *"18 de marzo de 2016"*. En otra el modelo cita una
  cláusula sin dar la fecha.
- La temperatura mueve la variabilidad, no la calidad. Para consultas sobre recursos públicos, donde
  la cifra o la fecha tiene que ser exacta, conviene 0–0,2.

### Experimento C: preguntas sin evidencia (`resultados/experimento_C.json`)

| Pregunta | ¿Rechazó? | Similitud máx. |
|---|---|---|
| ¿Cuál es el salario del director de INCIVA? | sí | 0,672 |
| ¿Cuál fue la facturación de INCIVA en 2017? | sí | 0,713 |
| ¿Cuántos empleados tiene INCIVA? | sí | 0,708 |
| ¿Cuántos visitantes recibió el Museo Arqueológico La Merced en 2024? | sí | 0,671 |
| ¿Quién ganó el mundial de fútbol de 2022? | sí | 0,594 |

El modelo **reconoció la falta de datos en 5 de 5 casos** (y en 3 de 3 en el experimento A, con
cualquier K), usando la frase que pide el prompt. Hay un detalle importante: la pregunta sobre la
facturación, que no tiene respuesta, obtuvo una similitud máxima (0,713) **mayor** que la de los
fragmentos que sí contienen la respuesta de N01 (0,702) y de I2 (0,662). Con estos embeddings, un umbral de similitud no sirve para separar preguntas con y
sin evidencia. El rechazo depende de las instrucciones del prompt, y ese mismo rechazo es el que
causa los rechazos indebidos de la sección 8.

### Experimento D: rendimiento (`resultados/experimento_D.json`)

Cada tanda empieza con el modelo sacado de memoria (`keep_alive: 0`). Pregunta N01, K = 3:

| Consultas | Total | 1ª consulta | Carga del modelo (1ª) | Media del resto | Carga media (resto) |
|---|---|---|---|---|---|
| 1 | 11,88 s | 11,88 s | 1,58 s | — | — |
| 5 | 37,93 s | 12,51 s | 1,58 s | 6,35 s | 0,005 s |
| 10 | 87,36 s | 11,90 s | 1,32 s | 8,38 s | 0,005 s |

La primera consulta de cada tanda cuesta alrededor de 12 s: 1,3–1,6 s de carga del modelo, más la
evaluación del prompt sin caché y una respuesta larga. Las siguientes bajan a 6–8 s. El *throughput*
es secuencial: diez consultas ≈ 87 s, porque Ollama en CPU atiende una a la vez. El costo por
consulta depende sobre todo de los **tokens de salida**, que varían entre corridas con la misma
pregunta.

## 10. Conclusiones (sustentadas en lo observado)

1. **La plataforma funciona de punta a punta.** Cinco servicios, 85 consultas trazadas en MLflow,
   métricas en Prometheus con el objetivo UP y un dashboard en Grafana. Todo corre en local, sin
   servicios de inferencia externos.
2. **La observabilidad sirvió para encontrar la causa.** Sin la traza, la respuesta de N01 parecía
   solo "mala". Con el span de recuperación se ve que el sistema trajo fragmentos sobre "valores
   ambientales". Con Prometheus y Grafana se detectó un *timeout* de 300 s que la media ocultaba en
   parte.
3. **El tiempo se va en generar, la calidad se pierde al recuperar.** El 98 % de la latencia es
   generación en CPU, pero los errores de contenido vienen de que el fragmento correcto queda en
   las posiciones 29–56. Subir K encarece la consulta sin arreglar esto.
4. **Más contexto no es mejor respuesta.** K = 3 y K = 5 aciertan lo mismo (2/9). K = 5 gasta un
   50 % más de tokens y agrega una respuesta inventada.
5. **La métrica automática no reemplaza la revisión humana.** La heurística de palabra clave
   sobreestimó los aciertos al triple (6 frente a 2). Una similitud alta tampoco indica
   pertinencia (0,713 en una pregunta sin evidencia).
6. **El prompt de rechazo funciona hacia ambos lados.** Evita inventar cuando no hay datos (8/8),
   pero produce rechazos indebidos cuando la recuperación falla (hasta 6/9 con K = 1).

### Mejoras que sugieren los datos (no aplicadas, para no alterar las mediciones)

- **Recuperación:** `nomic-embed-text` espera prefijos de tarea (`search_query:` / `search_document:`),
  que esta versión mínima no usa. También conviene usar búsqueda híbrida con BM25 (resolvería
  "valor" frente a "valores" y las cifras), un *reranker* y fragmentos más grandes que respeten las
  cláusulas. Es la arquitectura de la Capa 4 de mi tesis (bge-m3 + BM25 + bge-reranker-v2-m3).
- **Generación:** limitar `num_predict` para que un bucle no llegue al *timeout* de 300 s. Revisar
  también `num_ctx`: el contenedor trabaja con 2 048 tokens de contexto, suficiente aquí, pero
  justo para K ≥ 8.
- **Evaluación:** pasar de la revisión manual a métricas sistemáticas (RAGAS: *faithfulness*,
  *context precision/recall*) con un LLM juez distinto del generador, como en la Capa 6 de la tesis.
- **Operación:** fijar versiones de las imágenes en lugar de `latest` y cambiar la contraseña
  `admin` de Grafana antes de compartir el sistema.
