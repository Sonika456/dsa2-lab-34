"""Состояние «Начата» — поездка активна, тарификация идёт."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from domain.exceptions import InvariantViolation
from domain.states.base import TripState

if TYPE_CHECKING:
    from domain.trip import Trip


class Started(TripState):
    name = "Начата"
    allowed = frozenset({"pause", "finish"})

    def pause(self, trip: Trip) -> TripState:
        from domain.states.paused import Paused
        
        # Используем публичное свойство clock_snapshot вместо защищённого _clock_snapshot
        trip.pause_started_at = trip.clock_snapshot
        return Paused()

    def finish(self, trip: Trip, photo_ref: str) -> TripState:
        from domain.states.finished import Finished
        
        if not photo_ref:
            raise InvariantViolation("Фото самоката обязательно при завершении")
        
        # Используем публичное свойство clock_snapshot вместо защищённого _clock_snapshot
        if trip.clock_snapshot < trip.start_time:
            raise InvariantViolation(
                "Время завершения не может быть раньше времени начала"
            )
        
        trip.end_time = trip.clock_snapshot
        trip.photo_ref = photo_ref
        return Finished()