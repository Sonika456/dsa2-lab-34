"""
Объекты-значения (Value Objects) предметной области «Аренда самоката».
Все объекты неизменяемы (frozen=True), валидация выполняется в __post_init__.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from domain.exceptions import InvariantViolation


@dataclass(frozen=True)
class Location:
    """Географическая точка (широта, долгота).
    Инварианты: широта [-90; 90], долгота [-180; 180]."""
    latitude: float
    longitude: float

    def __post_init__(self):
        if not -90.0 <= self.latitude <= 90.0:
            raise InvariantViolation(
                f"Широта должна быть в диапазоне [-90; 90], "
                f"получено {self.latitude}"
            )
        if not -180.0 <= self.longitude <= 180.0:
            raise InvariantViolation(
                f"Долгота должна быть в диапазоне [-180; 180], "
                f"получено {self.longitude}"
            )


@dataclass(frozen=True)
class Tariff:
    """Тариф поездки.
    Инварианты: все ставки положительны, минимальная стоимость >= 0."""
    per_minute_rub: Decimal
    per_pause_minute_rub: Decimal  # сниженная ставка для паузы
    min_trip_cost_rub: Decimal

    def __post_init__(self):
        if self.per_minute_rub <= 0:
            raise InvariantViolation("Ставка за минуту должна быть > 0")
        if self.per_pause_minute_rub <= 0:
            raise InvariantViolation("Ставка паузы должна быть > 0")
        if self.per_pause_minute_rub >= self.per_minute_rub:
            raise InvariantViolation(
                "Ставка паузы должна быть ниже обычной ставки"
            )
        if self.min_trip_cost_rub < 0:
            raise InvariantViolation(
                "Минимальная стоимость не может быть отрицательной"
            )


@dataclass(frozen=True)
class TripCost:
    """Результат расчёта стоимости поездки.
    Инвариант: итоговая сумма >= 0."""
    total_rub: Decimal
    duration_minutes: int
    pause_minutes: int

    def __post_init__(self):
        if self.total_rub < 0:
            raise InvariantViolation("Стоимость не может быть отрицательной")
        if self.duration_minutes < 0:
            raise InvariantViolation("Длительность не может быть < 0")
        if self.pause_minutes < 0:
            raise InvariantViolation("Время паузы не может быть < 0")


# Константы регламента (могут быть вынесены в rules.yaml в Разделе IV)
BOOKING_TIMEOUT_MINUTES = 10
PREAUTHORIZATION_AMOUNT = Decimal("300")
LONG_TRIP_HOURS = 12
MIN_BATTERY_LEVEL = 20  # процент