FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home app
COPY search_blocking/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/flightgen.py search_blocking/main.py search_sync/routes.py ./
USER app
# Без sh -c: uvicorn становится процессом с PID 1, к нему подключается py-spy
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
