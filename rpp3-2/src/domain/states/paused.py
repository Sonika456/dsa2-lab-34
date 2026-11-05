"""Состояние «Приостановлена» — клиент поставил поездку на паузу.
Тарификация идёт по сниженной ставке."""
from __future__ import annotations

from typing import TYPE_CHECKING

from domain.states.base import TripState

if TYPE_CHECKING:
    from domain.trip import Trip


class Paused(TripState):
    name = "Приостановлена"
    allowed = frozenset({"resume"})

    def resume(self, trip: Trip) -> TripState:
        from domain.states.started import Started
        
        # Накопление времени паузы для расчёта стоимости
        if trip.pause_started_at is not None:
            # Используем публичное свойство clock_snapshot вместо защищённого _clock_snapshot
            pause_duration = trip.clock_snapshot - trip.pause_started_at
            trip.total_pause_seconds += int(pause_duration.total_seconds())
            trip.pause_started_at = None
        return Started()