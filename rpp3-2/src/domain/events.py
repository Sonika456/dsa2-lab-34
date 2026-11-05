"""
Доменные события — фиксация значимых для предметной области фактов.
Все события неизменяемы (frozen=True) и добавляются в журнал агрегата
при каждом переходе состояния.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TripBooked:
    """Поездка забронирована, самокат зарезервирован."""
    trip_id: UUID
    scooter_id: UUID
    user_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class TripDenied:
    """Поездка отклонена (общее событие для задолженности и платежа)."""
    trip_id: UUID
    occurred_at: datetime
    reason: str  # "Задолженность" или "Платёж"


@dataclass(frozen=True)
class TripCancelled:
    """Бронь снята по истечении 10 минут."""
    trip_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class TripStarted:
    """Поездка начата: замок разблокирован, тарификация запущена."""
    trip_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class TripPaused:
    """Поездка приостановлена клиентом (сниженная ставка)."""
    trip_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class TripResumed:
    """Поездка возобновлена клиентом."""
    trip_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class TripFinished:
    """Поездка завершена в разрешённой зоне, фото получено."""
    trip_id: UUID
    photo_ref: str
    occurred_at: datetime


@dataclass(frozen=True)
class TripCharged:
    """Стоимость поездки успешно списана."""
    trip_id: UUID
    amount: float
    occurred_at: datetime


@dataclass(frozen=True)
class TripUnpaid:
    """Списание не прошло, зафиксирована задолженность."""
    trip_id: UUID
    amount: float
    occurred_at: datetime


@dataclass(frozen=True)
class FinishRefused:
    """Отказ в завершении: зона парковки запрещена.
    Событие не меняет состояние (поездка остаётся «Начата»),
    но фиксируется в журнале."""
    trip_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ReceiptIssued:
    """Чек отправлен клиенту."""
    trip_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class TripTooLong:
    """Поездка длится более 12 часов, оператор уведомлён.
    Событие непрерывающего таймера: состояние поездки не меняется."""
    trip_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class SupportRequestOpened:
    """Зафиксировано обращение клиента по проблеме."""
    trip_id: UUID
    description: str
    occurred_at: datetime


@dataclass(frozen=True)
class SupportResponseSent:
    """Оператор отправил ответ клиенту по обращению."""
    trip_id: UUID
    resolution: str
    occurred_at: datetime