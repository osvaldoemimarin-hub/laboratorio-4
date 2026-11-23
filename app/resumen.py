"""Resume resultados/experimento_*.json en tablas Markdown (resultados/resumen.md)."""
import json
import statistics as st
from pathlib import Path

R = Path("resultados")


def cargar(nombre):
    ruta = R / f"experimento_{nombre}.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def media(xs):
    return st.mean(xs) if xs else 0.0


lineas = ["# Resumen de experimentos\n"]

a = cargar("A")
if a:
    lineas += ["## Experimento A: top_k\n",
               "| Indicador | K=1 | K=3 | K=5 |", "|---|---|---|---|"]
    filas = {
        "Tiempo RAG medio (s)": lambda rs: f"{media([r['tiempo_recuperacion'] for r in rs]):.3f}",
        "Tokens entrada medios": lambda rs: f"{media([r['tokens_entrada'] for r in rs]):.0f}",
        "Tokens salida medios": lambda rs: f"{media([r['tokens_salida'] for r in rs]):.0f}",
        "Generación media (s)": lambda rs: f"{media([r['duracion_generacion'] for r in rs]):.2f}",
        "Duración total media (s)": lambda rs: f"{media([r['duracion'] for r in rs]):.2f}",
        "Similitud máxima media": lambda rs: f"{media([r['similitud_max'] for r in rs]):.3f}",
        "Con dato clave (heurística)": lambda rs: (
            f"{sum(1 for r in rs if r['contiene_clave'])}/{sum(1 for r in rs if not r['sin_evidencia'])}"),
        "Rechazos correctos sin evidencia": lambda rs: (
            f"{sum(1 for r in rs if r['sin_evidencia'] and r['rechazo_detectado'])}/"
            f"{sum(1 for r in rs if r['sin_evidencia'])}"),
        "Rechazos indebidos (con evidencia)": lambda rs: (
            f"{sum(1 for r in rs if not r['sin_evidencia'] and r['rechazo_detectado'])}"),
    }
    for nombre, f in filas.items():
        lineas.append(f"| {nombre} | " + " | ".join(f(a[k]) for k in ("1", "3", "5")) + " |")
    lineas.append("\n### Detalle por pregunta (✔ = contiene el dato clave; R = rechazó)\n")
    lineas += ["| id | K=1 | K=3 | K=5 | fuentes K=3 |", "|---|---|---|---|---|"]
    por_id = {k: {r["id"]: r for r in a[k]} for k in a}

    def marca(r):
        if r is None:
            return "error"
        if r["rechazo_detectado"]:
            return "R"
        return "✔" if r["contiene_clave"] else "✘"

    for id_ in por_id["3"]:
        fuentes = ", ".join(sorted({f.split("#")[0].replace(".txt", "") for f in por_id["3"][id_]["fuentes"]}))
        lineas.append(f"| {id_} | " + " | ".join(marca(por_id[k].get(id_)) for k in ("1", "3", "5"))
                      + f" | {fuentes} |")

b = cargar("B")
if b:
    lineas += ["\n## Experimento B: temperatura\n",
               "| Temperatura | Respuestas distintas de 9 (3 preguntas × 3 rep.) | Tokens salida medios |",
               "|---|---|---|"]
    for t in (0.0, 0.5, 1.0):
        rs = [x for x in b if x["temperatura"] == t]
        distintas = sum(len({x["respuesta"].strip() for x in rs if x["pregunta"] == p})
                        for p in {x["pregunta"] for x in rs})
        lineas.append(f"| {t} | {distintas} | {media([x['tokens_salida'] for x in rs]):.0f} |")

c = cargar("C")
if c:
    lineas += ["\n## Experimento C: preguntas sin evidencia\n",
               "| Pregunta | ¿Rechazó? | Similitud máx. | Respuesta (inicio) |", "|---|---|---|---|"]
    for x in c:
        resp = x["respuesta"].replace("\n", " ").replace("|", "/")[:140]
        lineas.append(f"| {x['pregunta']} | {'sí' if x['rechazo_detectado'] else 'no'} | "
                      f"{x['similitud_max']:.3f} | {resp} |")

d = cargar("D")
if d:
    lineas += ["\n## Experimento D: rendimiento (cada tanda inicia con el modelo descargado)\n",
               "| N consultas | Total (s) | 1ª consulta (s) | Carga modelo 1ª (s) | Media resto (s) | Carga media resto (s) |",
               "|---|---|---|---|---|---|"]
    for n in ("1", "5", "10"):
        cs = d[n]["consultas"]
        resto = cs[1:]
        lineas.append(
            f"| {n} | {d[n]['total_segundos']:.2f} | {cs[0]['duracion_cliente']:.2f} | {cs[0]['duracion_carga']:.2f} | "
            f"{media([x['duracion_cliente'] for x in resto]):.2f} | {media([x['duracion_carga'] for x in resto]):.3f} |"
            if resto else
            f"| {n} | {d[n]['total_segundos']:.2f} | {cs[0]['duracion_cliente']:.2f} | {cs[0]['duracion_carga']:.2f} | - | - |")

(R / "resumen.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
print("\n".join(lineas))
