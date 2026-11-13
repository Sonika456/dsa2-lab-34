"""Синхронная версия сервиса поиска: def-обработчики, requests, SQLAlchemy Core (psycopg)."""
import os
import time
from datetime import date, datetime, timedelta

import requests
from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import BigInteger, Column, DateTime, MetaData, Numeric, String, Table, create_engine, select

from flightgen import AIRPORTS
from routes import Flight, build_routes

DATABASE_URL = os.environ["DATABASE_URL"]                 # postgresql+psycopg://...
SUPPLIERS = dict(item.split("=", 1) for item in os.environ["SUPPLIERS"].split(","))
SUPPLIER_BUDGET = float(os.getenv("SUPPLIER_BUDGET", "2.0"))   # на поставщика, с, включая повтор
RETRY_PAUSE = float(os.getenv("RETRY_PAUSE", "0.2"))           # пауза перед повтором, с

metadata = MetaData()
flights_table = Table(
    "flights", metadata,
    Column("id", BigInteger, primary_key=True),
    Column("carrier", String), Column("flight_no", String),
    Column("origin", String(3)), Column("destination", String(3)),
    Column("dep_time", DateTime), Column("arr_time", DateTime),
    Column("price", Numeric(10, 2)),
)
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)

http = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=40)
http.mount("http://", adapter)

app = FastAPI(title="Агрегатор поиска авиаперелётов (синхронная версия)")


class SupplierError(Exception):
    pass


def load_own_flights(day: date) -> list[Flight]:
    """Рейсы собственной базы за дату. Соединение занято только на время запроса."""
    start = datetime.combine(day, datetime.min.time())
    stmt = select(flights_table).where(flights_table.c.dep_time >= start,
                                       flights_table.c.dep_time < start + timedelta(days=1))
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    return [Flight(r.carrier, r.flight_no, r.origin.strip(), r.destination.strip(),
                   r.dep_time, r.arr_time, float(r.price)) for r in rows]


def fetch_supplier(url: str, day: date) -> list[Flight]:
    """Запрос к поставщику: на всё (запрос, пауза, повтор) отводится SUPPLIER_BUDGET секунд.
    Ошибка 500 -> один повтор через RETRY_PAUSE. Исключение -> поставщик не ответил."""
    deadline = time.monotonic() + SUPPLIER_BUDGET
    for attempt in (1, 2):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SupplierError("тайм-аут")
        try:
            # timeout= в requests задаётся отдельно для каждого вызова, поэтому
            # передаём остаток от общего срока.
            r = http.get(f"{url}/flights", params={"date": day.isoformat()}, timeout=remaining)
            r.raise_for_status()
            return [Flight(x["carrier"], x["flight_no"], x["origin"], x["destination"],
                           datetime.fromisoformat(x["dep_time"]),
                           datetime.fromisoformat(x["arr_time"]), float(x["price"]))
                    for x in r.json()]
        except requests.Timeout:
            raise SupplierError("тайм-аут")
        except (requests.RequestException, ValueError, KeyError) as exc:
            if attempt == 2 or deadline - time.monotonic() <= RETRY_PAUSE:
                raise SupplierError(str(exc))
            time.sleep(RETRY_PAUSE)                         # пауза перед повтором
    raise SupplierError("недостижимо")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/search")
async def search(origin: str = Query(pattern="^[A-Z]{3}$"),
           destination: str = Query(pattern="^[A-Z]{3}$"),
           day: date = Query(alias="date")):
    started = time.monotonic()
    if origin == destination or origin not in AIRPORTS or destination not in AIRPORTS:
        raise HTTPException(422, "неизвестный аэропорт или совпадают аэропорты вылета и прилёта")

    all_flights = load_own_flights(day)
    own_count = len(all_flights)

    failed: list[str] = []
    answered = 0
    for name, url in SUPPLIERS.items():                    # по очереди
        try:
            all_flights.extend(fetch_supplier(url, day))
            answered += 1
        except SupplierError:
            failed.append(name)

    if answered == 0 and own_count == 0:
        raise HTTPException(503, "поиск временно недоступен")

    routes = build_routes(all_flights, origin, destination, day)
    return {
        "routes": [{"total_price": r.total_price,
                    "flights": [{"carrier": f.carrier, "flight_no": f.flight_no,
                                 "origin": f.origin, "destination": f.destination,
                                 "dep_time": f.dep_time.isoformat(),
                                 "arr_time": f.arr_time.isoformat(),
                                 "price": f.price} for f in r.flights]} for r in routes],
        "failed_suppliers": failed,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
    }
