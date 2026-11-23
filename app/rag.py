"""RAG mínimo desde cero (Parte IV del laboratorio) sobre documentos de la tesis RAG-INCIVA.

Indexación: leer .txt -> fragmentar con solapamiento -> embeddings con Ollama -> datos/indice.json.
Consulta: embedding de la pregunta -> similitud coseno contra todos los fragmentos -> top_k.
"""
import json
import os
import time
from pathlib import Path

import mlflow
import numpy as np
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODELO_EMBEDDING = os.getenv("MODELO_EMBEDDING", "nomic-embed-text")
RUTA_DOCUMENTOS = Path(os.getenv("RUTA_DOCUMENTOS", "/documentos"))
RUTA_INDICE = Path(os.getenv("RUTA_INDICE", "/datos/indice.json"))
TAMANO_FRAGMENTO = int(os.getenv("TAMANO_FRAGMENTO", "500"))
SOLAPE_FRAGMENTO = int(os.getenv("SOLAPE_FRAGMENTO", "80"))

# Caché en memoria del índice para no releer el JSON (varios MB) en cada consulta.
_cache = {"mtime": None, "indice": None, "matriz": None}


# 1. Leer archivos TXT
def leer_documentos():
    documentos = []
    for archivo in sorted(RUTA_DOCUMENTOS.glob("*.txt")):
        documentos.append({
            "fuente": archivo.name,
            "texto": archivo.read_text(encoding="utf-8"),
        })
    return documentos


# 2. Dividir textos con solapamiento
def dividir_texto(texto, tamano=TAMANO_FRAGMENTO, solape=SOLAPE_FRAGMENTO):
    if tamano <= solape:
        raise ValueError("El tamaño debe superar el solape")
    fragmentos = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + tamano, len(texto))
        fragmentos.append(texto[inicio:fin])
        if fin == len(texto):
            break
        inicio = fin - solape
    return fragmentos


# 3. Embeddings mediante Ollama
def crear_embedding(texto):
    respuesta = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": MODELO_EMBEDDING, "input": texto},
        timeout=180,
    )
    respuesta.raise_for_status()
    return respuesta.json()["embeddings"][0]


# 4. Indexar documentos
def indexar_documentos():
    inicio = time.perf_counter()
    documentos = leer_documentos()
    if not documentos:
        raise FileNotFoundError(f"No hay archivos .txt en {RUTA_DOCUMENTOS}")
    indice = []
    for documento in documentos:
        fragmentos = dividir_texto(documento["texto"])
        for numero, fragmento in enumerate(fragmentos):
            indice.append({
                "fuente": documento["fuente"],
                "fragmento": numero + 1,
                "texto": fragmento,
                "embedding": crear_embedding(fragmento),
            })

    RUTA_INDICE.parent.mkdir(parents=True, exist_ok=True)
    RUTA_INDICE.write_text(
        json.dumps(indice, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "documentos": len(documentos),
        "fragmentos": len(indice),
        "tamano_fragmento": TAMANO_FRAGMENTO,
        "solape": SOLAPE_FRAGMENTO,
        "modelo_embedding": MODELO_EMBEDDING,
        "segundos": round(time.perf_counter() - inicio, 2),
    }


# 5. Comparar vectores
def similitud_coseno(vector_a, vector_b):
    a = np.array(vector_a, dtype=float)
    b = np.array(vector_b, dtype=float)
    denominador = np.linalg.norm(a) * np.linalg.norm(b)
    if denominador == 0:
        return 0.0
    return float(np.dot(a, b) / denominador)


def _cargar_indice():
    if not RUTA_INDICE.exists():
        raise FileNotFoundError("Primero debes indexar los documentos")
    mtime = RUTA_INDICE.stat().st_mtime
    if _cache["mtime"] != mtime:
        indice = json.loads(RUTA_INDICE.read_text(encoding="utf-8"))
        if not indice:
            raise ValueError("El índice está vacío")
        matriz = np.array([item["embedding"] for item in indice], dtype=float)
        matriz /= np.linalg.norm(matriz, axis=1, keepdims=True).clip(min=1e-12)
        _cache.update(mtime=mtime, indice=indice, matriz=matriz)
    return _cache["indice"], _cache["matriz"]


# 6. Recuperar los top_k fragmentos
@mlflow.trace(name="recuperar_documentos")
def recuperar_documentos(pregunta, top_k=3):
    inicio = time.perf_counter()
    indice, matriz = _cargar_indice()

    vector = np.array(crear_embedding(pregunta), dtype=float)
    vector /= max(np.linalg.norm(vector), 1e-12)
    similitudes = matriz @ vector  # coseno: vectores ya normalizados

    orden = np.argsort(-similitudes)[:top_k]
    resultados = [
        {
            "fuente": indice[i]["fuente"],
            "fragmento": indice[i]["fragmento"],
            "texto": indice[i]["texto"],
            "similitud": float(similitudes[i]),
        }
        for i in orden
    ]
    return {
        "fragmentos": resultados,
        "tiempo_recuperacion": time.perf_counter() - inicio,
    }
