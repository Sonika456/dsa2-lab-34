"""
Порты (протоколы) для внешних зависимостей.
Доменный и прикладной слои работают только с этими контрактами.
Конкретные реализации (In-Memory заглушки) находятся в инфраструктуре.
"""
from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.value_objects import Location


class Clock(Protocol):
    """Абстракция времени. В доменном и прикладном слоях
    ЗАПРЕЩЕНО использовать datetime.now() напрямую."""

    def now(self) -> datetime: ...


class PaymentGateway(Protocol):
    """Порт платёжного сервиса.
    В схеме BPMN платёжный сервис не является участником —
    это внешняя зависимость реализации."""

    def authorize(self, user_id: UUID, amount: float) -> bool:
        """Предварительная авторизация (предавторизация) на сумму 300 ₽."""
        ...

    def charge(self, user_id: UUID, amount: float) -> bool:
        """Фактическое списание стоимости поездки."""
        ...


class ZoneRegistry(Protocol):
    """Реестр зон парковки. Проверяет, разрешено ли завершить
    поездку в указанной точке."""

    def is_allowed(self, location: Location) -> bool: ...


class ScooterHardware(Protocol):
    """Порт взаимодействия с IoT-замком самоката."""

    def unlock(self, scooter_id: UUID) -> bool: ...