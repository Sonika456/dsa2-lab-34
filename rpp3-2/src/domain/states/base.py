"""
Базовый класс состояния агрегата Trip.
Все 9 событий из таблицы переходов объявлены здесь и по умолчанию запрещены.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from domain.exceptions import TransitionNotAllowed

if TYPE_CHECKING:
    from domain.trip import Trip


class TripState:
    """Абстрактное состояние поездки.
    name — человекочитаемое название (для status и журналирования).
    allowed — перечень событий, допустимых в этом состоянии."""

    name: str = ""
    allowed: frozenset[str] = frozenset()

    def _not_allowed(self, event: str) -> TripState:
        raise TransitionNotAllowed(self.name, event)

    # === Все 9 событий таблицы переходов ===
    def expire_booking(self, trip: Trip) -> TripState:
        return self._not_allowed("expire_booking")

    def deny_debt(self, trip: Trip) -> TripState:
        return self._not_allowed("deny_debt")

    def deny_payment(self, trip: Trip) -> TripState:
        return self._not_allowed("deny_payment")

    def start_trip(self, trip: Trip) -> TripState:
        return self._not_allowed("start_trip")

    def pause(self, trip: Trip) -> TripState:
        return self._not_allowed("pause")

    def resume(self, trip: Trip) -> TripState:
        return self._not_allowed("resume")

    def finish(self, trip: Trip, photo_ref: str) -> TripState:
        return self._not_allowed("finish")

    def charge_ok(self, trip: Trip) -> TripState:
        return self._not_allowed("charge_ok")

    def charge_fail(self, trip: Trip) -> TripState:
        return self._not_allowed("charge_fail")