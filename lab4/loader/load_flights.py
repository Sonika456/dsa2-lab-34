"""Загрузка рейсов собственной базы на 120 дней. Повторный запуск ничего не меняет."""
import os
from datetime import date, timedelta

from sqlalchemy import create_engine, text

from flightgen import generate_flights

DATABASE_URL = os.environ["DATABASE_URL"]
START_DATE = date.fromisoformat(os.getenv("START_DATE", "2026-11-01"))
DAYS = int(os.getenv("DAYS", "120"))
PER_DAY = int(os.getenv("FLIGHTS_PER_DAY", "1500"))

INSERT = text(
    "INSERT INTO flights (carrier, flight_no, origin, destination, dep_time, arr_time, price) "
    "VALUES (:carrier, :flight_no, :origin, :destination, :dep_time, :arr_time, :price) "
    "ON CONFLICT (carrier, flight_no, dep_time) DO NOTHING"
)


def main() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for d in range(DAYS):
            day = START_DATE + timedelta(days=d)
            conn.execute(INSERT, generate_flights("OWN", day, PER_DAY))
        total = conn.execute(text("SELECT count(*) FROM flights")).scalar_one()
    print(f"В таблице flights {total} рейсов (ожидается {DAYS * PER_DAY})")


if __name__ == "__main__":
    main()
