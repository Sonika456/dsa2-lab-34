"""Конечное состояние «Отменена по сроку».
Бронь не использована в течение 10 минут."""
from domain.states.base import TripState


class Cancelled(TripState):
    name = "Отменена по сроку"
    allowed = frozenset()