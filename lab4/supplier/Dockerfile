FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home app
COPY supplier/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/flightgen.py supplier/main.py ./
USER app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
