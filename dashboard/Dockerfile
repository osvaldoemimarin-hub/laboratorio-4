FROM python:3.11-slim

WORKDIR /dashboard
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY .streamlit/ .streamlit/
COPY static/ static/
COPY dashboard.py styles.css ./
EXPOSE 8501

CMD ["streamlit", "run", "dashboard.py"]
