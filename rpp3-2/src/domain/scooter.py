"""
Агрегат Scooter — электросамокат.
Доработка агрегата из ЛР2: добавлен статус «забронирован»
и методы резервирования/освобождения.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from domain.exceptions import InvariantViolation
from domain.value_objects import MIN_BATTERY_LEVEL


class ScooterStatus(str, Enum):
    """Статус самоката.
    В ЛР2 были только FREE и IN_SERVICE; добавлен RESERVED
    для поддержки 10-минутной брони."""
    FREE = "свободен"
    RESERVED = "забронирован"
    RENTED = "арендован"
    IN_SERVICE = "на обслуживании"


@dataclass
class Scooter:
    """Корень агрегата Scooter.
    Инварианты:
    - 0 <= battery_level <= 100;
    - аренда возможна только из статусов FREE и RESERVED;
    - самокат с зарядом ниже MIN_BATTERY_LEVEL не может быть арендован;
    - возврат возможен только из статуса RENTED.
    """
    scooter_id: UUID
    _battery_level: int
    _status: ScooterStatus = ScooterStatus.FREE

    # === Свойства только для чтения ===
    @property
    def battery_level(self) -> int:
        return self._battery_level

    @property
    def status(self) -> ScooterStatus:
        return self._status

    @property
    def is_available_for_rent(self) -> bool:
        """Предикат: самокат может быть забронирован."""
        return (
            self._status in (ScooterStatus.FREE, ScooterStatus.RESERVED)
            and self._battery_level >= MIN_BATTERY_LEVEL
        )

    # === Доменные методы ===
    def reserve(self) -> None:
        """Зарезервировать самокат на 10 минут.
        Допустимо только из статусов FREE."""
        if self._status != ScooterStatus.FREE:
            raise InvariantViolation(
                f"Зарезервировать можно только свободный самокат, "
                f"текущий статус: {self._status.value}"
            )
        if self._battery_level < MIN_BATTERY_LEVEL:
            raise InvariantViolation(
                f"Нельзя забронировать самокат с зарядом "
                f"{self._battery_level}% (порог {MIN_BATTERY_LEVEL}%)"
            )
        self._status = ScooterStatus.RESERVED

    def release(self) -> None:
        """Снять бронь (по таймеру 10 мин или при отказе в поездке).
        Допустимо только из статуса RESERVED."""
        if self._status != ScooterStatus.RESERVED:
            raise InvariantViolation(
                f"Снять бронь можно только с зарезервированного самоката, "
                f"текущий статус: {self._status.value}"
            )
        self._status = ScooterStatus.FREE

    def rent(self) -> None:
        """Начать аренду (разблокировать замок).
        Допустимо только из статуса RESERVED с достаточным зарядом."""
        if self._status != ScooterStatus.RESERVED:
            raise InvariantViolation(
                f"Начать аренду можно только с зарезервированного самоката, "
                f"текущий статус: {self._status.value}"
            )
        if self._battery_level < MIN_BATTERY_LEVEL:
            raise InvariantViolation(
                f"Нельзя арендовать самокат с зарядом "
                f"{self._battery_level}% (порог {MIN_BATTERY_LEVEL}%)"
            )
        self._status = ScooterStatus.RENTED

    def return_scooter(self) -> None:
        """Завершить аренду (самокат возвращён в зону парковки).
        Допустимо только из статуса RENTED."""
        if self._status != ScooterStatus.RENTED:
            raise InvariantViolation(
                f"Вернуть можно только арендованный самокат, "
                f"текущий статус: {self._status.value}"
            )
        self._status = ScooterStatus.FREE

    def send_to_service(self) -> None:
        """Отправить самокат на обслуживание."""
        if self._status == ScooterStatus.IN_SERVICE:
            raise InvariantViolation(
                "Самокат уже находится на обслуживании"
            )
        self._status = ScooterStatus.IN_SERVICE

    def discharge(self, percent: int) -> None:
        """Снизить уровень заряда (имитация расхода батареи во время поездки).
        В реальном проекте заряд обновляется от IoT-датчика."""
        if percent < 0:
            raise InvariantViolation("Расход батареи не может быть отрицательным")
        new_level = max(0, self._battery_level - percent)
        self._battery_level = new_level