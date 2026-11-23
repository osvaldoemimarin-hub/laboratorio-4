# Laboratorio 4 — LLMOps: RAG local con Ollama, MLflow, Prometheus y Grafana

Laboratorio de Gestión de Proyectos de IA (Maestría en IA y Ciencia de Datos, UAO), basado en la guía
*"LLMOps desde cero en Windows con WSL2 y Docker"* (J. M. Núñez Velasco). En lugar de la empresa
ficticia TecnoFábrica, el asistente consulta documentos reales del trabajo de grado de Osvaldo Marin: el **convenio
interadministrativo de educación ambiental 2017 entre la Gobernación del Valle (Secretaría de
Educación) e INCIVA** (tesis *"Arquitectura RAG de código abierto para consulta inteligente y
trazabilidad de recursos públicos en el proyecto de educación ambiental de INCIVA (2018–2025)"*).

Los resultados medidos y su análisis están en **[INFORME.md](INFORME.md)**.

## Arquitectura

```
Usuario ─► FastAPI (api:8000) ─► RAG: embeddings nomic-embed-text + coseno sobre datos/indice.json
                 │                      │
                 ├────────────────► Ollama (qwen2.5:1.5b, contenedor, CPU)
                 │
                 ├─ trazas ──► MLflow (5000)     pipeline_rag ─┬─ recuperar_documentos
                 │                                             └─ generar_respuesta_llm
                 └─ /metrics ◄── Prometheus (9090) ◄── Grafana (3000, dashboard precargado)
```

| Servicio | Imagen | URL en Windows |
|---|---|---|
| ollama | `ollama/ollama` | http://localhost:11435 (ver nota) |
| mlflow | `./mlflow` (python 3.11 + mlflow 3) | http://localhost:5000 |
| api | `./app` (FastAPI) | http://localhost:8000/docs |
| prometheus | `prom/prometheus` | http://localhost:9090 |
| grafana | `grafana/grafana` (admin/admin) | http://localhost:3000 |

## Adaptaciones respecto a la guía

| Guía | Este repositorio | Motivo |
|---|---|---|
| TecnoFábrica (3 TXT ficticios) | 6 documentos del convenio INCIVA 2017 (≈254 mil caracteres, 606 fragmentos) | Usar el caso de la tesis |
| Ollama en `127.0.0.1:11434` | `127.0.0.1:11435` → 11434 del contenedor | El 11434 del host lo ocupa el Ollama nativo de la tesis (GPU AMD); dentro de la red Docker la API sigue usando `http://ollama:11434` |
| Proyecto en `~/proyectos` de Ubuntu (WSL) | Carpeta de Windows con Docker Desktop (motor WSL2) | No hay distribución Ubuntu instalada; los comandos son los mismos desde PowerShell/Git Bash |
| `recuperar_documentos` relee el JSON en cada consulta | Caché en memoria del índice + producto matricial | 606 vectores × 768 dims: misma similitud coseno, menos latencia |
| Dashboard creado a mano | `grafana/provisioning/dashboards/llmops.json` con los 6 paneles del paso 27 + p95 y tasa de tokens | Reproducible |
| `evaluacion.py` | + columnas heurísticas `contiene_clave` / `rechazo_detectado`, parámetros `--top-k`/`--temperatura` | Apoyo a la calificación manual |
| — | `app/experimentos.py` y `app/resumen.py` | Experimentos A–D del paso 30 reproducibles |

## Datos y privacidad

`documentos/*.txt` se generan con `scripts/preparar_corpus.py` a partir del texto ya extraído (capa
nativa u OCR) en la caché de la tesis, aplicando el anonimizador de la tesis
(`rag_inciva.ingestion.privacidad.anonimizar`: cédulas, vecindad, lugar de expedición) y un
enmascarado adicional de correos y restos de cédula cortados por el OCR. Solo se incluyen documentos
institucionales del convenio (no contratos individuales, listados de asistencia ni hojas de vida).
Son documentos públicos de contratación estatal; los nombres que aparecen son los de los
funcionarios firmantes.

Las preguntas de `datos/preguntas_evaluacion.csv` y sus respuestas de referencia salen del
`gold_standard.yaml` de la tesis (ids G1, G2, G4, I1, I2, N01–N04, F2, F4, F5).

## Cómo ejecutarlo

Requisitos: Docker Desktop con motor WSL2 y Python 3.11 en el host (solo para los scripts de evaluación).

```powershell
docker compose build
docker compose up -d
docker compose ps

docker compose exec ollama ollama pull qwen2.5:1.5b
docker compose exec ollama ollama pull nomic-embed-text

curl.exe -X POST http://localhost:8000/indexar        # ~1 min en CPU: 6 documentos, 606 fragmentos

py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install requests
.\.venv\Scripts\python.exe app\evaluacion.py           # datos/resultados.json
.\.venv\Scripts\python.exe app\experimentos.py A B C D # resultados/experimento_*.json (~15 min)
.\.venv\Scripts\python.exe app\resumen.py              # resultados/resumen.md
```

> En Git Bash para Windows, `curl -d` con tildes envía el cuerpo en la página de códigos local y
> FastAPI responde 400; usar Swagger (`/docs`) o los scripts de Python para preguntar.

Detener sin borrar datos: `docker compose down` (no usar `-v`, que borra modelos y métricas).

## Estructura

```
├── docker-compose.yml
├── app/            main.py, rag.py, metricas.py, evaluacion.py, experimentos.py, resumen.py, Dockerfile
├── mlflow/         Dockerfile
├── prometheus/     prometheus.yml
├── grafana/provisioning/{datasources,dashboards}/
├── documentos/     corpus INCIVA anonimizado (.txt)
├── datos/          preguntas_evaluacion.csv, resultados.json (indice.json se regenera, no se versiona)
├── resultados/     JSON de los experimentos y resumen.md
├── evidencias/     salidas de verificación (ollama list, tokens, consulta, métricas, trazas, PromQL) y capturas
├── scripts/        preparar_corpus.py
└── INFORME.md      entregables del paso 32 y conclusiones
```
