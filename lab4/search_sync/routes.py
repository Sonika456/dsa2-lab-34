"""Составление маршрутов. Чистая функция: не обращается к сети и базе данных."""
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta
from heapq import nsmallest
from typing import NamedTuple

MIN_LAYOVER = timedelta(hours=1)
MAX_LAYOVER = timedelta(hours=6)


class Flight(NamedTuple):
    carrier: str
    flight_no: str
    origin: str
    destination: str
    dep_time: datetime
    arr_time: datetime
    price: float


class Route(NamedTuple):
    flights: tuple[Flight, ...]
    total_price: float


def build_routes(flights: list[Flight], origin: str, destination: str,
                 day: date, limit: int = 20, max_legs: int = 3) -> list[Route]:
    """Прямые маршруты и маршруты не более чем с двумя пересадками (max_legs = 3 рейса).

    Все рейсы вылетают в дату поиска; пересадка выполняется в аэропорту прилёта
    предыдущего рейса, между рейсами от 1 до 6 часов; аэропорты не повторяются.
    Возвращает limit самых дешёвых маршрутов или пустой список."""
    by_origin: dict[str, list[Flight]] = {}
    for f in flights:
        if f.dep_time.date() == day:
            by_origin.setdefault(f.origin, []).append(f)
    dep_index: dict[str, list[datetime]] = {}
    for airport, lst in by_origin.items():
        lst.sort(key=lambda f: f.dep_time)
        dep_index[airport] = [f.dep_time for f in lst]

    found: list[Route] = []

    def extend(path: list[Flight], visited: set[str], price: float) -> None:
        last = path[-1]
        if last.destination == destination:
            found.append(Route(tuple(path), price))
            return
        if len(path) == max_legs:
            return
        nxt = by_origin.get(last.destination)
        if not nxt:
            return
        times = dep_index[last.destination]
        lo = bisect_left(times, last.arr_time + MIN_LAYOVER)
        hi = bisect_right(times, last.arr_time + MAX_LAYOVER)
        for f in nxt[lo:hi]:
            if f.destination in visited:
                continue
            path.append(f)
            visited.add(f.destination)
            extend(path, visited, price + f.price)
            visited.discard(f.destination)
            path.pop()

    for first in by_origin.get(origin, []):
        extend([first], {origin, first.destination}, first.price)

    return nsmallest(limit, found, key=lambda r: (r.total_price, r.flights[0].dep_time))
