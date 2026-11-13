"""Асинхронный опрос поставщика: общий срок через asyncio.timeout, повтор после asyncio.sleep."""
import asyncio
import time
from datetime import date, datetime

import httpx

from routes import Flight


class SupplierError(Exception):
    pass


def parse_flights(data: list[dict]) -> list[Flight]:
    return [Flight(x["carrier"], x["flight_no"], x["origin"], x["destination"],
                   datetime.fromisoformat(x["dep_time"]),
                   datetime.fromisoformat(x["arr_time"]), float(x["price"])) for x in data]


async def fetch_supplier(client: httpx.AsyncClient, url: str, day: date,
                         budget: float = 2.0, pause: float = 0.2) -> list[Flight]:
    """На всё (запрос, пауза, повтор) отводится budget секунд.
    Ошибка 500 -> один повтор через pause. Любая неудача -> SupplierError."""
    deadline = time.monotonic() + budget
    try:
        async with asyncio.timeout(budget):                 # ограничивает блок целиком
            for attempt in (1, 2):
                try:
                    r = await client.get(f"{url}/flights", params={"date": day.isoformat()})
                    r.raise_for_status()
                    return parse_flights(r.json())
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    # повтор имеет смысл, только если после паузы ещё останется время
                    if attempt == 2 or deadline - time.monotonic() <= pause:
                        raise SupplierError(str(exc) or type(exc).__name__) from exc
                    await asyncio.sleep(pause)              # не time.sleep!
    except TimeoutError:
        raise SupplierError("тайм-аут") from None
    raise SupplierError("недостижимо")
