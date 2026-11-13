"""Заглушка поставщика. Параметры задаются переменными окружения."""
import asyncio
import os
import random
from datetime import date

from fastapi import FastAPI, HTTPException

from flightgen import generate_flights

NAME = os.getenv("SUPPLIER_NAME", "supplier1")
MEAN_DELAY_MS = float(os.getenv("MEAN_DELAY_MS", "300"))
JITTER = float(os.getenv("DELAY_JITTER", "0.3"))        # ±30 %
ERROR_PCT = float(os.getenv("ERROR_PCT", "5"))          # ответы 500
SLOW_PCT = float(os.getenv("SLOW_PCT", "0"))            # ответы через SLOW_DELAY_S
SLOW_DELAY_S = float(os.getenv("SLOW_DELAY_S", "3"))
FLIGHTS_PER_DAY = int(os.getenv("FLIGHTS_PER_DAY", "500"))

app = FastAPI(title=f"Заглушка {NAME}")


@app.get("/health")
async def health():
    return {"status": "ok", "supplier": NAME}


@app.get("/flights")
async def flights(date: date):
    # Задержки и ошибки определяет модуль random без начального значения,
    # не связанный с данными: повторный запрос может завершиться успешно.
    r = random.random() * 100
    if r < SLOW_PCT:
        await asyncio.sleep(SLOW_DELAY_S)
    else:
        delay = MEAN_DELAY_MS * random.uniform(1 - JITTER, 1 + JITTER) / 1000
        await asyncio.sleep(delay)                       # не time.sleep!
        if r < SLOW_PCT + ERROR_PCT:
            raise HTTPException(status_code=500, detail="supplier error")
    # Рейсы зависят только от перевозчика и даты: одинаковы при повторных запросах.
    return generate_flights(NAME, date, FLIGHTS_PER_DAY, seed="supplier")
