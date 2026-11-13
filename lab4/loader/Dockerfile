FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home app
COPY loader/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/flightgen.py loader/load_flights.py ./
USER app
CMD ["python", "load_flights.py"]
