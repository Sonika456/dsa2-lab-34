"""
Агрегат Trip — поездка на электросамокате.
Ключевая сущность предметной области. Реализует паттерн «Состояние»:
текущий объект состояния хранится в закрытом атрибуте _state,
все события делегируются состоянию, которое возвращает новый объект.
Публичного сеттера у статуса нет — изменить состояние в обход методов
событий физически невозможно.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from domain.events import (
    TripBooked, TripDenied, TripCancelled, TripStarted,
    TripPaused, TripResumed, TripFinished, TripCharged,
    TripUnpaid, FinishRefused, TripTooLong,
    SupportRequestOpened, SupportResponseSent,
)
from domain.exceptions import InvariantViolation
from domain.states.base import TripState
from domain.states.booked import Booked
from domain.value_objects import Tariff, TripCost, BOOKING_TIMEOUT_MINUTES


@dataclass
class SupportRequest:
    """Обращение клиента в поддержку в рамках поездки.
    Встроено в агрегат Trip как внутренняя сущность."""
    description: str
    opened_at: datetime
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None

    @property
    def is_resolved(self) -> bool:
        return self.resolution is not None


@dataclass
class Trip:
    """Корень агрегата Trip.
    Инварианты:
    - start_time выставляется только при старте поездки (не в конструкторе);
    - end_time >= start_time;
    - photo_ref обязателен при завершении;
    - переход в состояние «Начата» возможен только после завершения
      обеих параллельных ветвей (замок + тарификация);
    - пауза тарифицируется по сниженной ставке;
    - открыто не более одного необработанного обращения в поддержку.
    """
    trip_id: UUID
    scooter_id: UUID
    user_id: UUID
    created_at: datetime

    # === Внутреннее состояние (паттерн State) ===
    _state: TripState = field(default_factory=Booked, repr=False)
    _events: list = field(default_factory=list, repr=False)

    # === Поля для параллельных ветвей (замок + тарификация) ===
    lock_released: bool = field(default=False)
    billing_started: bool = field(default=False)

    # === Временные метки поездки ===
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    pause_started_at: Optional[datetime] = None
    total_pause_seconds: int = 0

    # === Данные завершения ===
    photo_ref: Optional[str] = None

    # === Служебные поля ===
    authorization_id: Optional[str] = None
    operator_notified: bool = False
    operator_contacted: bool = False
    active_support_request: Optional[SupportRequest] = None

    # === Снимок времени (передаётся состоянию для инвариантов) ===
    _clock_snapshot: Optional[datetime] = field(default=None, repr=False)

    # =========================================================
    # Свойства только для чтения
    # =========================================================
    @property
    def status(self) -> str:
        """Человекочитаемое название текущего состояния."""
        return self._state.name

    @property
    def allowed_events(self) -> frozenset[str]:
        """Перечень событий, допустимых в текущем состоянии.
        Используется для:
        - проверки истечения таймеров (POST /internal/tick);
        - отображения доступных операций в GET-ответе."""
        return self._state.allowed

    @property
    def events(self) -> tuple:
        """Журнал доменных событий (неизменяемый срез)."""
        return tuple(self._events)

    @property
    def clock_snapshot(self) -> Optional[datetime]:
        """Снимок текущего времени, переданный состоянию.
        Используется состояниями для проверки инвариантов хронологии."""
        return self._clock_snapshot

    @property
    def current_pause_started_at(self) -> Optional[datetime]:
        """Момент начала текущей паузы (если поездка приостановлена)."""
        return self.pause_started_at

    @property
    def duration_seconds(self) -> int:
        """Общая длительность поездки в секундах (без пауз)."""
        if self.start_time is None:
            return 0
        end = self.end_time if self.end_time is not None else datetime.utcnow()
        total = int((end - self.start_time).total_seconds())
        return max(0, total - self.total_pause_seconds)

    # =========================================================
    # Методы событий — делегирование состоянию
    # =========================================================
    def _set_clock(self, now: datetime) -> None:
        """Передать состоянию снимок текущего времени.
        Используется для проверки инвариантов хронологии."""
        self._clock_snapshot = now

    def on_booking_expired(self, now: datetime) -> None:
        """Событие таймера 10 мин: бронь не использована.
        Инвариант: срабатывает только если прошло >= BOOKING_TIMEOUT_MINUTES."""
        if (now - self.created_at).total_seconds() < BOOKING_TIMEOUT_MINUTES * 60:
            return  # срок ещё не истёк
        self._set_clock(now)
        self._state = self._state.expire_booking(self)
        self._events.append(TripCancelled(self.trip_id, now))

    def deny_debt(self, now: datetime) -> None:
        """Отказ из-за задолженности клиента."""
        self._set_clock(now)
        self._state = self._state.deny_debt(self)
        self._events.append(TripDenied(self.trip_id, now, "Задолженность"))

    def deny_payment(self, now: datetime) -> None:
        """Отказ из-за непрошедшей предавторизации."""
        self._set_clock(now)
        self._state = self._state.deny_payment(self)
        self._events.append(TripDenied(self.trip_id, now, "Платёж"))

    def start_trip(self, now: datetime) -> None:
        """Поездка начата (параллельное слияние).
        Инвариант проверяется внутри состояния Booked."""
        self._set_clock(now)
        self._state = self._state.start_trip(self)
        self.start_time = now
        self._events.append(TripStarted(self.trip_id, now))

    def pause(self, now: datetime) -> None:
        """Клиент поставил поездку на паузу."""
        self._set_clock(now)
        self._state = self._state.pause(self)
        # pause_started_at устанавливается внутри состояния Paused
        self._events.append(TripPaused(self.trip_id, now))

    def resume(self, now: datetime) -> None:
        """Клиент возобновил поездку."""
        self._set_clock(now)
        self._state = self._state.resume(self)
        # total_pause_seconds обновляется внутри состояния Paused
        self._events.append(TripResumed(self.trip_id, now))

    def finish(self, photo_ref: str, now: datetime) -> None:
        """Завершить поездку в разрешённой зоне."""
        self._set_clock(now)
        self._state = self._state.finish(self, photo_ref)
        # end_time и photo_ref устанавливаются внутри состояния Started
        self._events.append(TripFinished(self.trip_id, photo_ref, now))

    def record_finish_refused(self, now: datetime) -> None:
        """Отказ в завершении из-за запрещённой зоны.
        Состояние НЕ меняется (поездка остаётся «Начата»),
        но фиксируется доменное событие."""
        self._events.append(FinishRefused(self.trip_id, now))

    def charge_ok(self, now: datetime) -> None:
        """Стоимость успешно списана."""
        self._set_clock(now)
        self._state = self._state.charge_ok(self)
        self._events.append(TripCharged(self.trip_id, Decimal("0"), now))

    def charge_fail(self, now: datetime) -> None:
        """Списание не прошло, зафиксирована задолженность."""
        self._set_clock(now)
        self._state = self._state.charge_fail(self)
        self._events.append(TripUnpaid(self.trip_id, Decimal("0"), now))

    # =========================================================
    # Методы для параллельных ветвей (не меняют состояние)
    # =========================================================
    def mark_lock_released(self) -> None:
        """Зафиксировать завершение ветви «Разблокировать замок»."""
        self.lock_released = True

    def mark_billing_started(self, now: datetime) -> None:
        """Зафиксировать завершение ветви «Запустить тарификацию».
        Одновременно выставляется start_time для расчёта длительности."""
        self.billing_started = True
        # start_time будет окончательно установлен при start_trip()

    def record_authorization(self, auth_id: str) -> None:
        """Сохранить идентификатор успешной предавторизации."""
        self.authorization_id = auth_id

    # =========================================================
    # Непрерывающий таймер 12 ч (ветвь оператора)
    # =========================================================
    def on_trip_too_long(self, now: datetime) -> None:
        """Событие непрерывающего таймера 12 ч.
        Состояние поездки НЕ меняется — поездка продолжается.
        Фиксируется только доменное событие и флаг уведомления."""
        if self.operator_notified:
            return  # повторное уведомление запрещено
        if self.start_time is None:
            return
        elapsed_hours = (now - self.start_time).total_seconds() / 3600
        if elapsed_hours < 12:
            return
        self.operator_notified = True
        self._events.append(TripTooLong(self.trip_id, now))

    # =========================================================
    # Обращения в поддержку (ветвь оператора)
    # =========================================================
    def record_operator_contact(self, has_problem: bool, now: datetime) -> None:
        """Зафиксировать факт связи оператора с клиентом."""
        self.operator_contacted = True
        if not has_problem and self.active_support_request is None:
            # Проблем нет, обращение не открываем
            pass

    def open_support_request(self, description: str, now: datetime) -> None:
        """Открыть обращение в поддержку.
        Инварианты:
        - не более одного необработанного обращения;
        - поездка не в конечном состоянии."""
        if self.active_support_request is not None:
            if not self.active_support_request.is_resolved:
                raise InvariantViolation(
                    "Уже есть открытое необработанное обращение"
                )
        self.active_support_request = SupportRequest(
            description=description, opened_at=now
        )
        self._events.append(SupportRequestOpened(self.trip_id, description, now))

    def resolve_support_request(
        self, resolution: str, now: datetime
    ) -> None:
        """Закрыть обращение ответом оператора.
        Инвариант: обращение должно быть открыто."""
        if self.active_support_request is None:
            raise InvariantViolation("Нет открытого обращения")
        if self.active_support_request.is_resolved:
            raise InvariantViolation("Обращение уже закрыто")
        self.active_support_request.resolution = resolution
        self.active_support_request.resolved_at = now
        self._events.append(
            SupportResponseSent(self.trip_id, resolution, now)
        )

    # =========================================================
    # Расчёт стоимости поездки
    # =========================================================
    def calculate_cost(self, tariff: Tariff) -> TripCost:
        """Рассчитать стоимость поездки по тарифу.
        Инвариант: итоговая сумма >= минимальной стоимости поездки."""
        if self.start_time is None:
            raise InvariantViolation(
                "Нельзя рассчитать стоимость: поездка не начата"
            )
        if self.end_time is None:
            raise InvariantViolation(
                "Нельзя рассчитать стоимость: поездка не завершена"
            )

        total_seconds = int((self.end_time - self.start_time).total_seconds())
        total_minutes = max(0, total_seconds // 60)
        pause_minutes = max(0, self.total_pause_seconds // 60)
        active_minutes = max(0, total_minutes - pause_minutes)

        active_cost = Decimal(active_minutes) * tariff.per_minute_rub
        pause_cost = Decimal(pause_minutes) * tariff.per_pause_minute_rub
        raw_total = active_cost + pause_cost

        total = max(raw_total, tariff.min_trip_cost_rub)
        return TripCost(
            total_rub=total,
            duration_minutes=total_minutes,
            pause_minutes=pause_minutes,
        )