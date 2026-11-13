"""Нагрузочный скрипт: замкнутый и открытый режимы, опрос /health каждые 100 мс.

Замкнутый:  python load.py --mode closed --clients 10
Открытый:   python load.py --mode open --rate 5
"""
import argparse
import asyncio
import math
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent / "common"))
from flightgen import AIRPORTS  # noqa: E402


def percentile(values: list[float], p: float) -> float:
    """Метод ближайшего ранга: значение с номером ceil(p/100 * n) в отсортированном списке."""
    if not values:
        return float("nan")
    s = sorted(values)
    return s[max(1, math.ceil(p / 100 * len(s))) - 1]


class Stats:
    def __init__(self) -> None:
        self.times: list[float] = []      # время ответа успешных и ошибочных, мс
        self.errors = 0

    def add(self, ms: float, ok: bool) -> None:
        self.times.append(ms)
        if not ok:
            self.errors += 1

    def report(self, duration: float) -> dict:
        n = len(self.times)
        return {
            "n": n, "rps": n / duration,
            "p50": percentile(self.times, 50), "p95": percentile(self.times, 95),
            "p99": percentile(self.times, 99), "max": max(self.times, default=float("nan")),
            "err_pct": 100 * self.errors / n if n else float("nan"),
        }


def make_params(rnd: random.Random, start: date, days: int) -> dict:
    origin, destination = rnd.sample(AIRPORTS, 2)
    return {"origin": origin, "destination": destination,
            "date": (start + timedelta(days=rnd.randrange(days))).isoformat()}


async def one_request(client: httpx.AsyncClient, url: str, params: dict | None,
                      timeout: float) -> tuple[float, bool]:
    t0 = time.perf_counter()
    try:
        async with asyncio.timeout(timeout):              # общий тайм-аут клиента
            r = await client.get(url, params=params)
        ok = r.status_code < 400                          # 4xx и 5xx считаются ошибкой
    except (asyncio.TimeoutError, httpx.HTTPError):
        ok = False
    return (time.perf_counter() - t0) * 1000, ok


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--mode", choices=["closed", "open"], required=True)
    ap.add_argument("--clients", type=int, default=10)
    ap.add_argument("--rate", type=float, default=5.0, help="запросов в секунду (открытый режим)")
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--warmup", type=float, default=10)
    ap.add_argument("--timeout", type=float, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start-date", default="2026-11-01")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--health-interval", type=float, default=0.1)
    a = ap.parse_args()

    start_day = date.fromisoformat(a.start_date)
    search_url, health_url = f"{a.url}/search", f"{a.url}/health"
    limits = httpx.Limits(max_connections=5000, max_keepalive_connections=200)
    search_stats, health_stats = Stats(), Stats()
    t_start = time.perf_counter()
    t_measure = t_start + a.warmup                        # начало учитываемого интервала
    t_end = t_measure + a.duration

    async with httpx.AsyncClient(limits=limits, timeout=None) as client, \
               httpx.AsyncClient(limits=limits, timeout=None) as hclient:

        async def record(stats: Stats, started: float, res: tuple[float, bool]) -> None:
            if t_measure <= started < t_end:              # прогрев не учитывается
                stats.add(*res)

        async def closed_client(idx: int) -> None:
            rnd = random.Random(a.seed + idx)
            while time.perf_counter() < t_end:
                started = time.perf_counter()
                res = await one_request(client, search_url, make_params(rnd, start_day, a.days), a.timeout)
                await record(search_stats, started, res)

        async def open_generator() -> None:
            rnd = random.Random(a.seed)
            pending: set[asyncio.Task] = set()

            async def fire(params: dict) -> None:
                started = time.perf_counter()
                res = await one_request(client, search_url, params, a.timeout)
                await record(search_stats, started, res)

            next_at = time.perf_counter()
            while next_at < t_end:
                delay = next_at - time.perf_counter()
                if delay > 0:
                    await asyncio.sleep(delay)
                task = asyncio.create_task(fire(make_params(rnd, start_day, a.days)))
                pending.add(task)
                task.add_done_callback(pending.discard)
                next_at += rnd.expovariate(a.rate)        # экспоненциальные интервалы
            if pending:
                await asyncio.wait(pending)

        async def health_poller() -> None:
            while time.perf_counter() < t_end:
                started = time.perf_counter()
                res = await one_request(hclient, health_url, None, a.timeout)
                await record(health_stats, started, res)
                await asyncio.sleep(max(0.0, a.health_interval - (time.perf_counter() - started)))

        workers = ([closed_client(i) for i in range(a.clients)] if a.mode == "closed"
                   else [open_generator()])
        await asyncio.gather(*workers, health_poller())

    s, h = search_stats.report(a.duration), health_stats.report(a.duration)
    mode = f"C = {a.clients}" if a.mode == "closed" else f"{a.rate:g} запросов/с"
    print(f"Режим: {a.mode} ({mode}); замер {a.duration:g} с, прогрев {a.warmup:g} с, "
          f"тайм-аут {a.timeout:g} с, начальное значение {a.seed}")
    print(f"{'':10}{'запросов':>9}{'зап/с':>8}{'p50,мс':>9}{'p95,мс':>9}{'p99,мс':>9}{'макс,мс':>10}{'ошибки,%':>10}")
    for name, r in (("search", s), ("/health", h)):
        print(f"{name:10}{r['n']:>9}{r['rps']:>8.2f}{r['p50']:>9.0f}{r['p95']:>9.0f}"
              f"{r['p99']:>9.0f}{r['max']:>10.0f}{r['err_pct']:>10.1f}")
    print("Перцентили: метод ближайшего ранга")


if __name__ == "__main__":
    asyncio.run(main())
