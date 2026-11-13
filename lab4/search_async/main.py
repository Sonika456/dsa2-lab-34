"""Асинхронная версия сервиса поиска: httpx.AsyncClient, SQLAlchemy async + asyncpg, gather."""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from sqlalchemy import BigInteger, Column, DateTime, MetaData, Numeric, String, Table, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from flightgen import AIRPORTS
from routes import Flight, build_routes
from suppliers import SupplierError, fetch_supplier

log = logging.getLogger("search")

DATABASE_URL = os.environ["DATABASE_URL"]                 # postgresql+asyncpg://...
SUPPLIERS = dict(item.split("=", 1) for item in os.environ["SUPPLIERS"].split(","))
SUPPLIER_BUDGET = float(os.getenv("SUPPLIER_BUDGET", "2.0"))
RETRY_PAUSE = float(os.getenv("RETRY_PAUSE", "0.2"))

metadata = MetaData()
flights_table = Table(
    "flights", metadata,
    Column("id", BigInteger, primary_key=True),
    Column("carrier", String), Column("flight_no", String),
    Column("origin", String(3)), Column("destination", String(3)),
    Column("dep_time", DateTime), Column("arr_time", DateTime),
    Column("price", Numeric(10, 2)),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Клиент и движок создаются один раз: пулы соединений переиспользуются.
    # Пул httpx с запасом: ожидание свободного соединения не должно съедать
    # время, отведённое поставщику. Тайм-аут запроса задаёт asyncio.timeout.
    app.state.http = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=500, max_keepalive_connections=100),
        timeout=httpx.Timeout(SUPPLIER_BUDGET + 1))
    app.state.engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=10)
    yield
    await app.state.http.aclose()
    await app.state.engine.dispose()


app = FastAPI(title="Агрегатор поиска авиаперелётов (асинхронная версия)", lifespan=lifespan)


async def load_own_flights(engine: AsyncEngine, day: date) -> list[Flight]:
    """Соединение занято только на время запроса."""
    start = datetime.combine(day, datetime.min.time())
    stmt = select(flights_table).where(flights_table.c.dep_time >= start,
                                       flights_table.c.dep_time < start + timedelta(days=1))
    async with engine.connect() as conn:
        rows = (await conn.execute(stmt)).all()
    return [Flight(r.carrier, r.flight_no, r.origin.strip(), r.destination.strip(),
                   r.dep_time, r.arr_time, float(r.price)) for r in rows]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/search")
async def search(request: Request,
                 origin: str = Query(pattern="^[A-Z]{3}$"),
                 destination: str = Query(pattern="^[A-Z]{3}$"),
                 day: date = Query(alias="date")):
    started = time.monotonic()
    if origin == destination or origin not in AIRPORTS or destination not in AIRPORTS:
        raise HTTPException(422, "неизвестный аэропорт или совпадают аэропорты вылета и прилёта")

    http: httpx.AsyncClient = request.app.state.http
    names = list(SUPPLIERS)

    # База и все поставщики опрашиваются одновременно. return_exceptions=True:
    # ошибка одного участника не прерывает остальных, а возвращается в списке.
    results = await asyncio.gather(
        load_own_flights(request.app.state.engine, day),
        *(fetch_supplier(http, SUPPLIERS[n], day, SUPPLIER_BUDGET, RETRY_PAUSE) for n in names),
        return_exceptions=True,
    )
    own, supplier_results = results[0], results[1:]

    all_flights: list[Flight] = []
    if isinstance(own, BaseException):
        log.warning("база данных недоступна: %r", own)
        own_count = 0
    else:
        all_flights.extend(own)
        own_count = len(own)

    failed: list[str] = []
    for name, res in zip(names, supplier_results):
        if isinstance(res, BaseException):
            failed.append(name)
        else:
            all_flights.extend(res)

    if len(failed) == len(names) and own_count == 0:
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
