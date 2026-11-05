"""Состояние «Забронирована» — начальное состояние поездки.
Самокат зарезервирован на 10 минут, идут проверки перед началом."""
from __future__ import annotations

from typing import TYPE_CHECKING

from domain.exceptions import InvariantViolation
from domain.states.base import TripState
from domain.states.cancelled import Cancelled
from domain.states.rejected_debt import RejectedDebt
from domain.states.rejected_payment import RejectedPayment
from domain.states.started import Started

if TYPE_CHECKING:
    from domain.trip import Trip


class Booked(TripState):
    name = "Забронирована"
    allowed = frozenset({
        "expire_booking",   # таймер 10 мин
        "deny_debt",        # шлюз «Есть задолженность?» -> да
        "deny_payment",     # шлюз «Предавторизация прошла?» -> нет
        "start_trip",       # параллельное слияние
    })

    def expire_booking(self, trip: Trip) -> TripState:
        return Cancelled()

    def deny_debt(self, trip: Trip) -> TripState:
        return RejectedDebt()

    def deny_payment(self, trip: Trip) -> TripState:
        return RejectedPayment()

    def start_trip(self, trip: Trip) -> TripState:
        # Инвариант параллельного слияния:
        # переход только когда обе ветви завершены
        if not (trip.lock_released and trip.billing_started):
            raise InvariantViolation(
                "Переход в «Начата» возможен только после завершения "
                "обеих параллельных ветвей (замок + тарификация)"
            )
        return Started()