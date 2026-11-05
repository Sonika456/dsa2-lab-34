"""Состояние «Завершена» — поездка в разрешённой зоне,
ожидает списания стоимости."""
from __future__ import annotations

from typing import TYPE_CHECKING

from domain.states.base import TripState
from domain.states.paid import Paid
from domain.states.unpaid import Unpaid

if TYPE_CHECKING:
    from domain.trip import Trip


class Finished(TripState):
    name = "Завершена"
    allowed = frozenset({"charge_ok", "charge_fail"})

    def charge_ok(self, trip: Trip) -> TripState:
        return Paid()

    def charge_fail(self, trip: Trip) -> TripState:
        return Unpaid()