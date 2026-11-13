"""Детерминированный генератор рейсов (общий для БД и заглушек поставщиков)."""
import random
from datetime import date, datetime, time, timedelta

AIRPORTS = [
    "OVB", "SVO", "DME", "VKO", "LED", "KJA", "SVX", "KZN", "AER", "KRR",
    "ROV", "UFA", "OMS", "TJM", "IKT", "VVO", "KHV", "GOJ", "KUF", "MRV",
    "CEK", "PEE", "NJC", "SGC", "BAX", "ABA", "YKS", "UUD", "HTA", "KGD",
]  # 30 аэропортов


def generate_flights(carrier: str, day: date, count: int, seed: str = "lab4") -> list[dict]:
    """Рейсы перевозчика за сутки. Одинаковые аргументы дают одинаковый результат:
    генератор создаётся с начальным значением, зависящим от перевозчика и даты."""
    rnd = random.Random(f"{seed}-{carrier}-{day.isoformat()}")
    midnight = datetime.combine(day, time.min)
    flights = []
    for i in range(1, count + 1):
        origin, destination = rnd.sample(AIRPORTS, 2)
        dep = midnight + timedelta(minutes=rnd.randrange(0, 1440))
        duration = rnd.randint(60, 360)                 # 1-6 часов
        arr = dep + timedelta(minutes=duration)
        price = 1500 + duration * 12 + rnd.randint(0, 4000)
        flights.append({
            "carrier": carrier,
            "flight_no": f"{carrier}-{i:04d}",
            "origin": origin,
            "destination": destination,
            "dep_time": dep,
            "arr_time": arr,
            "price": price,
        })
    return flights
