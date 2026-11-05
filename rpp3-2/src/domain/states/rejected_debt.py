"""Конечное состояние «Отклонена: задолженность».
У клиента есть неоплаченные прошлые поездки."""
from domain.states.base import TripState


class RejectedDebt(TripState):
    name = "Отклонена: задолженность"
    allowed = frozenset()