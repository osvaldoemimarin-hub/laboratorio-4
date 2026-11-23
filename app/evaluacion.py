"""Evaluación con preguntas de referencia (Parte X). Se corre desde la raíz del laboratorio:

    python app/evaluacion.py [--top-k 3] [--temperatura 0.2] [--salida datos/resultados.json]

Recopila evidencia; NO mide exactitud semántica. `contiene_clave` y `rechazo_detectado` son solo
ayudas heurísticas: la calificación final (correcta / incompleta / inventada) se hace a mano
contrastando con los documentos (ver INFORME.md).
"""
import argparse
import csv
import json
import time
import unicodedata
from pathlib import Path

import requests

API_URL = "http://localhost:8000/preguntar"
RUTA_PREGUNTAS = Path("datos/preguntas_evaluacion.csv")
FRASE_RECHAZO = "no existe información suficiente"


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def evaluar(top_k: int, temperatura: float, salida: Path) -> list[dict]:
    resultados = []
    with RUTA_PREGUNTAS.open(encoding="utf-8", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            inicio = time.perf_counter()
            try:
                respuesta = requests.post(
                    API_URL,
                    json={"pregunta": fila["pregunta"], "top_k": top_k, "temperatura": temperatura},
                    timeout=360,
                )
                respuesta.raise_for_status()
                datos = respuesta.json()
                generada = datos["respuesta"]
                claves = [c for c in fila["claves"].split("|") if c]
                resultados.append({
                    "id": fila["id"],
                    "pregunta": fila["pregunta"],
                    "esperada": fila["respuesta_esperada"],
                    "generada": generada,
                    "sin_evidencia": fila["sin_evidencia"] == "1",
                    "contiene_clave": any(normalizar(c) in normalizar(generada) for c in claves) if claves else None,
                    "rechazo_detectado": normalizar(FRASE_RECHAZO) in normalizar(generada),
                    "fuentes": [f"{f['fuente']}#{f['fragmento']}" for f in datos["fuentes"]],
                    "similitud_max": max(f["similitud"] for f in datos["fuentes"]),
                    "top_k": top_k,
                    "temperatura": temperatura,
                    "tokens_entrada": datos["tokens_entrada"],
                    "tokens_salida": datos["tokens_salida"],
                    "tiempo_recuperacion": datos["tiempo_recuperacion"],
                    "duracion_generacion": datos["duracion_generacion"],
                    "duracion": time.perf_counter() - inicio,
                })
                print(f"Pregunta {fila['id']} completada")
            except requests.RequestException as error:
                print(f"Error en pregunta {fila['id']}: {error}")

    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Evaluacion terminada -> {salida}")
    return resultados


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--temperatura", type=float, default=0.2)
    p.add_argument("--salida", type=Path, default=Path("datos/resultados.json"))
    a = p.parse_args()
    evaluar(a.top_k, a.temperatura, a.salida)
