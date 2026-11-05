"""Конечное состояние «Не оплачена».
Списание не прошло, зафиксирована задолженность, аккаунт заблокирован."""
from domain.states.base import TripState


class Unpaid(TripState):
    name = "Не оплачена"
    allowed = frozenset()