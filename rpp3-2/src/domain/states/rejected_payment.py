"""Конечное состояние «Отклонена: платёж».
Предавторизация на 300 ₽ не прошла."""
from domain.states.base import TripState


class RejectedPayment(TripState):
    name = "Отклонена: платёж"
    allowed = frozenset()