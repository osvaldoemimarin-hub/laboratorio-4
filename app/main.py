"""API del asistente documental (Parte VI): FastAPI + RAG + Ollama + MLflow + Prometheus."""
import os
import time
from contextlib import asynccontextmanager

import mlflow
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from metricas import (
    CONSULTAS,
    DURACION_RAG,
    DURACION_TOTAL,
    SIMILITUD_RAG,
    TOKENS_ENTRADA,
    TOKENS_SALIDA,
)
from rag import indexar_documentos, recuperar_documentos

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MLFLOW_URL = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MODELO = os.getenv("MODELO_LLM", "qwen2.5:1.5b")
EXPERIMENTO = os.getenv("MLFLOW_EXPERIMENTO", "Laboratorio_RAG_Ollama")

mlflow.set_tracking_uri(MLFLOW_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MLflow puede tardar en iniciar: esperamos a que esté disponible
    for intento in range(20):
        try:
            mlflow.set_experiment(EXPERIMENTO)
            print("MLflow conectado")
            break
        except Exception as error:
            if intento == 19:
                raise
            print("Esperando MLflow:", error)
            time.sleep(2)
    yield


app = FastAPI(
    title="Laboratorio LLMOps - RAG INCIVA",
    description="Ollama + RAG + Observabilidad sobre el convenio de educación ambiental INCIVA 2017",
    version="1.0",
    lifespan=lifespan,
)


class Pregunta(BaseModel):
    pregunta: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)
    temperatura: float = Field(default=0.2, ge=0, le=2)


@app.get("/")
def inicio():
    return {"mensaje": "Plataforma LLMOps activa", "modelo": MODELO}


@app.get("/health")
def health():
    return {"estado": "ok"}


@app.post("/indexar")
def indexar():
    try:
        return indexar_documentos()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


INSTRUCCIONES = """
Eres un asistente documental de INCIVA (Instituto para la Investigación y la Preservación del
Patrimonio Cultural y Natural del Valle del Cauca) para el proyecto de educación ambiental.
Responde exclusivamente con la información del contexto documental.
Si el contexto no contiene la respuesta, responde: "No existe información suficiente en los
documentos para responder esta pregunta."
Indica el nombre del archivo fuente que respalda tu respuesta. Responde en español y de forma clara.
"""


@mlflow.trace(name="generar_respuesta_llm")
def generar_respuesta(pregunta, fragmentos, temperatura):
    contexto = "\n\n".join(
        f"Fuente: {item['fuente']}\nContenido: {item['texto']}"
        for item in fragmentos
    )

    prompt = f"""
CONTEXTO:
{contexto}

PREGUNTA:
{pregunta}

RESPUESTA:
"""

    respuesta = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": MODELO,
            "system": INSTRUCCIONES,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperatura},
        },
        timeout=300,
    )
    respuesta.raise_for_status()
    datos = respuesta.json()

    return {
        "respuesta": datos["response"],
        "tokens_entrada": datos.get("prompt_eval_count", 0),
        "tokens_salida": datos.get("eval_count", 0),
        "duracion_ollama": datos.get("total_duration", 0) / 1e9,
        "duracion_generacion": datos.get("eval_duration", 0) / 1e9,
        "duracion_carga": datos.get("load_duration", 0) / 1e9,
    }


@mlflow.trace(name="pipeline_rag")
def ejecutar_rag(datos: Pregunta):
    recuperacion = recuperar_documentos(
        pregunta=datos.pregunta,
        top_k=datos.top_k,
    )
    fragmentos = recuperacion["fragmentos"]

    respuesta = generar_respuesta(
        pregunta=datos.pregunta,
        fragmentos=fragmentos,
        temperatura=datos.temperatura,
    )

    DURACION_RAG.observe(recuperacion["tiempo_recuperacion"])
    for fragmento in fragmentos:
        SIMILITUD_RAG.observe(fragmento["similitud"])

    TOKENS_ENTRADA.inc(respuesta["tokens_entrada"])
    TOKENS_SALIDA.inc(respuesta["tokens_salida"])

    return {
        "pregunta": datos.pregunta,
        "respuesta": respuesta["respuesta"],
        "top_k": datos.top_k,
        "temperatura": datos.temperatura,
        "modelo": MODELO,
        "tokens_entrada": respuesta["tokens_entrada"],
        "tokens_salida": respuesta["tokens_salida"],
        "duracion_ollama": respuesta["duracion_ollama"],
        "duracion_generacion": respuesta["duracion_generacion"],
        "duracion_carga": respuesta["duracion_carga"],
        "tiempo_recuperacion": recuperacion["tiempo_recuperacion"],
        "fuentes": fragmentos,
    }


@app.post("/preguntar")
def preguntar(datos: Pregunta):
    inicio = time.perf_counter()
    try:
        resultado = ejecutar_rag(datos)
        CONSULTAS.labels(estado="exito").inc()
        return resultado
    except Exception as error:
        CONSULTAS.labels(estado="error").inc()
        raise HTTPException(status_code=500, detail=str(error))
    finally:
        DURACION_TOTAL.observe(time.perf_counter() - inicio)


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
