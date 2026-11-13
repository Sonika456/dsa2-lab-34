FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home app
COPY search_async/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/flightgen.py search_sync/routes.py search_async/main.py search_async/suppliers.py ./
USER app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
