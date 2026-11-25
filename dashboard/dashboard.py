import os
from pathlib import Path

import requests
import streamlit as st


API_URL = os.getenv("RAG_API_URL", "http://localhost:8000").rstrip("/")
STYLES = Path(__file__).with_name("styles.css")
PREGUNTAS_GUIA = {
    "Objeto del convenio": "¿Cuál es el objeto del convenio de educación ambiental de 2017?",
    "Obligaciones de INCIVA": "¿Qué obligaciones asumió INCIVA en el convenio?",
    "Valor del convenio": "¿Cuál fue el valor total del convenio y cómo se financió?",
}


@st.cache_data(ttl=10, show_spinner=False)
def obtener_modelo():
    try:
        respuesta = requests.get(f"{API_URL}/", timeout=(2, 3))
        respuesta.raise_for_status()
        datos = respuesta.json()
        return datos.get("modelo") if isinstance(datos, dict) else None
    except (requests.RequestException, ValueError):
        return None


def consultar_rag(pregunta, top_k, temperatura):
    try:
        respuesta = requests.post(
            f"{API_URL}/preguntar",
            json={"pregunta": pregunta, "top_k": top_k, "temperatura": temperatura},
            timeout=(5, 500),
        )
    except requests.Timeout as error:
        raise RuntimeError("El RAG tardó demasiado en responder. Intenta de nuevo.") from error
    except requests.RequestException as error:
        raise RuntimeError("No se pudo conectar con el servicio RAG.") from error

    try:
        datos = respuesta.json()
    except ValueError as error:
        raise RuntimeError(f"La API devolvió una respuesta inválida (HTTP {respuesta.status_code}).") from error

    if not isinstance(datos, dict):
        raise RuntimeError(f"La API devolvió una respuesta inválida (HTTP {respuesta.status_code}).")
    if not respuesta.ok:
        detalle = datos.get("detail", "")
        if detalle in ("Primero debes indexar los documentos", "El índice está vacío"):
            raise RuntimeError("El corpus requiere indexación. Ejecuta `curl.exe -X POST http://localhost:8000/indexar`.")
        if isinstance(detalle, str) and detalle:
            raise RuntimeError(detalle)
        raise RuntimeError(f"La consulta falló (HTTP {respuesta.status_code}).")
    return datos


def cargar_pregunta(pregunta):
    st.session_state.pregunta = pregunta


def mostrar_resultado(resultado):
    with st.container(key="resultado", border=True):
        st.subheader("Respuesta")
        st.text(resultado["pregunta"])
        st.markdown(resultado["respuesta"])

        st.subheader(f"Fuentes recuperadas ({len(resultado['fuentes'])})")
        for fuente in resultado["fuentes"]:
            with st.expander(f"{fuente['fuente']} · Fragmento {fuente['fragmento']}"):
                st.caption(f"Similitud coseno · {fuente['similitud']:.3f}")
                st.text(fuente["texto"])

        st.subheader("Métricas de la consulta")
        recuperacion, generacion, entrada, salida = st.columns(4)
        recuperacion.metric("Recuperación", f"{resultado['tiempo_recuperacion']:.2f} s")
        generacion.metric("Generación", f"{resultado['duracion_generacion']:.2f} s")
        entrada.metric("Tokens de entrada", resultado["tokens_entrada"])
        salida.metric("Tokens de salida", resultado["tokens_salida"])
        st.caption(f"Modelo {resultado['modelo']} · Top K {resultado['top_k']} · Temperatura {resultado['temperatura']:.1f}")


st.set_page_config(page_title="ContractFlow | NEXORIUM", page_icon=":material/description:", layout="wide")
st.html(STYLES)

with st.sidebar:
    st.html('''
        <div class="producto">Contract<span>Flow</span></div>
        <div class="etiqueta marca">NEXORIUM</div>
    ''')
    st.markdown("---")
    st.subheader("Configuración RAG")
    top_k = st.slider("Fragmentos (Top K)", 1, 10, 3)
    temperatura = st.slider("Temperatura", 0.0, 2.0, 0.2, step=0.1)
    st.markdown("---")
    st.link_button("Abrir Grafana", "http://localhost:3000", icon=":material/monitoring:")

modelo = obtener_modelo()
with st.container(key="encabezado", horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
    st.html('<div class="etiqueta seccion">CONTRACTFLOW / CONSULTAS</div>', width="content")
    if modelo:
        st.html('<div class="estado conectado">API conectada</div>', width="content")
    else:
        st.html('<div class="estado">API sin conexión</div>', width="content")

st.html('''
    <section class="hero" aria-labelledby="titulo">
        <div class="hero-texto">
            <div class="etiqueta">CONVENIO INCIVA · 2017</div>
            <h1 id="titulo">Asistente<br>documental<span>.</span></h1>
            <p>Consulta el convenio de educación ambiental y revisa los fragmentos que respaldan cada respuesta.</p>
        </div>
        <div class="hero-arte">
            <img src="app/static/nexorium.webp" alt="NEXORIUM — Intelligence Beyond Boundaries" width="960" height="320">
        </div>
    </section>
''')

consulta, sugerencias = st.columns([2, 1], gap="medium")
with consulta:
    with st.form("consulta", border=True):
        st.subheader("Consulta al RAG")
        pregunta = st.text_area(
            "Escribe tu pregunta", key="pregunta", height=110,
            placeholder="¿Qué obligaciones establece el convenio?",
        )
        enviar = st.form_submit_button("Consultar", type="primary", icon=":material/arrow_forward:")
    if enviar and not pregunta.strip():
        st.warning("Escribe una pregunta para consultar el corpus.")
    elif enviar:
        with st.spinner("Recuperando fragmentos y generando la respuesta…"):
            try:
                st.session_state.resultado = consultar_rag(pregunta.strip(), top_k, temperatura)
            except RuntimeError as error:
                st.error(str(error))

with sugerencias, st.container(key="sugerencias", border=True):
    st.subheader("Preguntas sugeridas")
    for etiqueta, ejemplo in PREGUNTAS_GUIA.items():
        st.button(etiqueta, width="stretch", icon=":material/north_west:", on_click=cargar_pregunta, args=(ejemplo,))

if "resultado" in st.session_state:
    mostrar_resultado(st.session_state.resultado)
