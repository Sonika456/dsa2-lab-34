"""
In-Memory реализации репозиториев.
Хранят агрегаты в словарях Python. Используются для демонстрации
и тестирования до вынесения в БД в Разделе IV.
"""
from typing import Optional
from uuid import UUID

from domain.user import User
from domain.scooter import Scooter
from domain.trip import Trip
from domain.exceptions import EntityNotFound


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, User] = {}

    def get(self, user_id: UUID) -> Optional[User]:
        return self._store.get(user_id)

    def save(self, user: User) -> None:
        self._store[user.user_id] = user

    def all(self) -> list[User]:
        return list(self._store.values())

    def get_or_fail(self, user_id: UUID) -> User:
        user = self.get(user_id)
        if user is None:
            raise EntityNotFound("User", user_id)
        return user


class InMemoryScooterRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Scooter] = {}

    def get(self, scooter_id: UUID) -> Optional[Scooter]:
        return self._store.get(scooter_id)

    def save(self, scooter: Scooter) -> None:
        self._store[scooter.scooter_id] = scooter

    def all(self) -> list[Scooter]:
        return list(self._store.values())

    def get_or_fail(self, scooter_id: UUID) -> Scooter:
        scooter = self.get(scooter_id)
        if scooter is None:
            raise EntityNotFound("Scooter", scooter_id)
        return scooter


class InMemoryTripRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Trip] = {}

    def get(self, trip_id: UUID) -> Optional[Trip]:
        return self._store.get(trip_id)

    def save(self, trip: Trip) -> None:
        self._store[trip.trip_id] = trip

    def all(self) -> list[Trip]:
        return list(self._store.values())

    def get_or_fail(self, trip_id: UUID) -> Trip:
        trip = self.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)
        return trip