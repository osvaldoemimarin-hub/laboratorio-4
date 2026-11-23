"""Experimentos controlados (Parte XI, paso 30). Desde la raíz del laboratorio:

    python app/experimentos.py A B C D

A: top_k 1, 3 y 5 sobre todas las preguntas de referencia.
B: temperatura 0, 0.5 y 1, tres repeticiones por pregunta, para ver la variabilidad.
C: preguntas sin evidencia en los documentos (¿reconoce la ausencia o inventa?).
D: rendimiento con 1, 5 y 10 consultas secuenciales, arrancando cada tanda en frío.
Cada experimento escribe resultados/experimento_<X>.json; resumen.py los resume en tablas.
"""
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from evaluacion import evaluar, normalizar, FRASE_RECHAZO  # noqa: E402

API = "http://localhost:8000"
OLLAMA_HOST = "http://localhost:11435"  # contenedor ollama publicado en el host
MODELO = "qwen2.5:1.5b"
SALIDA = Path("resultados")


def preguntar(pregunta, top_k=3, temperatura=0.2):
    inicio = time.perf_counter()
    r = requests.post(f"{API}/preguntar",
                      json={"pregunta": pregunta, "top_k": top_k, "temperatura": temperatura},
                      timeout=360)
    r.raise_for_status()
    d = r.json()
    d["duracion_cliente"] = time.perf_counter() - inicio
    d["fuentes"] = [{k: f[k] for k in ("fuente", "fragmento", "similitud")} for f in d["fuentes"]]
    return d


def descargar_modelo():
    """Saca el LLM de memoria (keep_alive=0) para medir el arranque en frío."""
    requests.post(f"{OLLAMA_HOST}/api/generate", json={"model": MODELO, "keep_alive": 0}, timeout=60)
    time.sleep(2)


def guardar(nombre, datos):
    SALIDA.mkdir(exist_ok=True)
    ruta = SALIDA / f"experimento_{nombre}.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {ruta}")


def experimento_a():
    datos = {}
    for k in (1, 3, 5):
        print(f"[A] top_k={k}")
        datos[str(k)] = evaluar(k, 0.2, SALIDA / f"evaluacion_topk{k}.json")
    guardar("A", datos)


def experimento_b():
    preguntas = [
        "¿Cuál es el objeto del convenio de educación ambiental firmado en 2017?",
        "¿Cuándo se firmó el acta de inicio del convenio?",
        "¿Qué actividades se realizaron con las instituciones educativas de Buga?",
    ]
    datos = []
    for t in (0.0, 0.5, 1.0):
        for p in preguntas:
            for rep in range(3):
                print(f"[B] t={t} rep={rep + 1} {p[:40]}")
                d = preguntar(p, 3, t)
                datos.append({"temperatura": t, "repeticion": rep + 1, "pregunta": p,
                              "respuesta": d["respuesta"], "tokens_salida": d["tokens_salida"],
                              "duracion_generacion": d["duracion_generacion"]})
    guardar("B", datos)


def experimento_c():
    preguntas = [
        "¿Cuál es el salario del director de INCIVA?",
        "¿Cuál fue la facturación de INCIVA en 2017?",
        "¿Cuántos empleados tiene INCIVA?",
        "¿Cuántos visitantes recibió el Museo Arqueológico La Merced en 2024?",
        "¿Quién ganó el mundial de fútbol de 2022?",
    ]
    datos = []
    for p in preguntas:
        print(f"[C] {p}")
        d = preguntar(p, 3, 0.2)
        datos.append({"pregunta": p, "respuesta": d["respuesta"],
                      "rechazo_detectado": normalizar(FRASE_RECHAZO) in normalizar(d["respuesta"]),
                      "similitud_max": max(f["similitud"] for f in d["fuentes"]),
                      "fuentes": d["fuentes"]})
    guardar("C", datos)


def experimento_d():
    pregunta = "¿Cuál es el valor del convenio interadministrativo de educación ambiental de 2017?"
    datos = {}
    for n in (1, 5, 10):
        descargar_modelo()
        corrida = []
        inicio = time.perf_counter()
        for i in range(n):
            d = preguntar(pregunta, 3, 0.2)
            corrida.append({"consulta": i + 1, "duracion_cliente": d["duracion_cliente"],
                            "duracion_ollama": d["duracion_ollama"],
                            "duracion_carga": d["duracion_carga"],
                            "duracion_generacion": d["duracion_generacion"],
                            "tiempo_recuperacion": d["tiempo_recuperacion"],
                            "tokens_entrada": d["tokens_entrada"],
                            "tokens_salida": d["tokens_salida"]})
        print(f"[D] n={n} total={time.perf_counter() - inicio:.1f}s")
        datos[str(n)] = {"total_segundos": time.perf_counter() - inicio, "consultas": corrida}
    guardar("D", datos)


if __name__ == "__main__":
    elegidos = [x.upper() for x in sys.argv[1:]] or ["A", "B", "C", "D"]
    for x in elegidos:
        {"A": experimento_a, "B": experimento_b, "C": experimento_c, "D": experimento_d}[x]()
