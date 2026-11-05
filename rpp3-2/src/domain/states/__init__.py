"""Пакет состояний агрегата Trip."""
from domain.states.base import TripState
from domain.states.booked import Booked
from domain.states.started import Started
from domain.states.paused import Paused
from domain.states.finished import Finished
from domain.states.paid import Paid
from domain.states.unpaid import Unpaid
from domain.states.rejected_debt import RejectedDebt
from domain.states.rejected_payment import RejectedPayment
from domain.states.cancelled import Cancelled

__all__ = [
    "TripState",
    "Booked", "Started", "Paused", "Finished",
    "Paid", "Unpaid",
    "RejectedDebt", "RejectedPayment", "Cancelled",
]