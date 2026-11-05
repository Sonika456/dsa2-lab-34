"""Конечное состояние «Оплачена». Переходов нет."""
from domain.states.base import TripState


class Paid(TripState):
    name = "Оплачена"
    allowed = frozenset()