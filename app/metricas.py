"""Métricas Prometheus (Parte V). Los tokens son solo los de generación del LLM, no los de embeddings."""
from prometheus_client import Counter, Histogram

CONSULTAS = Counter(
    "llm_consultas_total",
    "Cantidad de consultas procesadas",
    ["estado"],
)

TOKENS_ENTRADA = Counter(
    "llm_tokens_entrada_total",
    "Tokens de entrada reportados por Ollama",
)

TOKENS_SALIDA = Counter(
    "llm_tokens_salida_total",
    "Tokens de salida reportados por Ollama",
)

DURACION_TOTAL = Histogram(
    "llm_duracion_segundos",
    "Duracion total de las consultas",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)

DURACION_RAG = Histogram(
    "rag_recuperacion_segundos",
    "Tiempo de recuperacion documental",
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10),
)

SIMILITUD_RAG = Histogram(
    "rag_similitud",
    "Similitud de fragmentos recuperados",
    buckets=(0, 0.2, 0.4, 0.6, 0.8, 0.9, 1),
)
