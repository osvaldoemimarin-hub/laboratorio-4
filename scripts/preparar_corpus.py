"""Prepara el corpus del laboratorio a partir del texto ya extraído (caché) de la tesis RAG-INCIVA.

Toma solo documentos institucionales del convenio de educación ambiental de 2017 (sin contratos
individuales ni listados de asistencia), aplica el anonimizador de la tesis (cédulas, vecindad y
lugar de expedición) y escribe un .txt por documento en documentos/.

Uso (desde la raíz del laboratorio, con el venv de la tesis que trae sus dependencias):
    <tesis>/.venv/Scripts/python.exe scripts/preparar_corpus.py --tesis <ruta_tesis>
"""
import argparse
import json
import re
import sys
from pathlib import Path

# (archivo de caché, nombre del .txt de salida, título)
DOCUMENTOS = [
    ("DOCS_GOBER__C_PROCESO_17-12-6757518_276000001_30481244_convenio.pdf.json",
     "convenio_2017.txt", "CONVENIO INTERADMINISTRATIVO DE EDUCACIÓN AMBIENTAL 2017"),
    ("DOCS_GOBER__DA_PROCESO_17-12-6757518_276000001_30822638_acta inicio.pdf.json",
     "acta_inicio_convenio_2017.txt", "ACTA DE INICIO DEL CONVENIO 2017"),
    ("DOCS_GOBER__DA_PROCESO_17-12-6757518_276000001_30482673_estudios_previos.pdf.json",
     "estudios_previos_2017.txt", "ESTUDIOS PREVIOS DEL CONVENIO 2017"),
    ("DOCS_GOBER__DA_PROCESO_17-12-6757518_276000001_30482655_matriz_riesgo.pdf.json",
     "matriz_riesgo_2017.txt", "MATRIZ DE RIESGOS DEL PROCESO 2017"),
    ("INFORME DE ACTIVIDADES__informe de actividades.pdf.json",
     "informe_actividades_2017.txt", "INFORME DE ACTIVIDADES DEL CONVENIO 2017"),
    ("INFORME DE SUPERVISION__informe de supervision .pdf.json",
     "informe_supervision_2017.txt", "INFORME DE SUPERVISIÓN DEL CONVENIO 2017"),
]


_CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# Restos de cédula que el anonimizador de la tesis no cubre (p. ej. "C.C. No. 16" cortado por OCR).
_CC_RESTO = re.compile(r"(C\.?\s?C\.?\s*(?:No\.?|N°)?\s*)\d[\d.,]*")


def limpiar(texto: str) -> str:
    texto = _CORREO.sub("[correo omitido]", texto)
    texto = _CC_RESTO.sub(r"\1[cédula omitida]", texto)
    texto = texto.replace("\t", " ")
    texto = re.sub(r"[ ]{2,}", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tesis", required=True, type=Path)
    p.add_argument("--salida", default=Path("documentos"), type=Path)
    a = p.parse_args()
    sys.path.insert(0, str(a.tesis / "src"))
    from rag_inciva.ingestion.privacidad import anonimizar, residuos_cedula  # noqa: E402

    a.salida.mkdir(parents=True, exist_ok=True)
    for cache, nombre, titulo in DOCUMENTOS:
        paginas = json.loads((a.tesis / "data" / "processed" / cache).read_text(encoding="utf-8"))
        partes = [f"{titulo} - INCIVA\n"]
        total = 0
        for pag in paginas:
            texto, n = anonimizar(pag.get("text") or "")
            total += n
            texto = limpiar(texto)
            if texto:
                partes.append(f"[Página {pag['page_number']}]\n{texto}")
        salida = "\n\n".join(partes) + "\n"
        residuos = residuos_cedula(salida)
        if residuos:
            raise SystemExit(f"{nombre}: quedan posibles cédulas {residuos[:3]}")
        (a.salida / nombre).write_text(salida, encoding="utf-8")
        print(f"{nombre}: {len(paginas)} páginas, {len(salida)} caracteres, {total} reemplazos")


if __name__ == "__main__":
    main()
