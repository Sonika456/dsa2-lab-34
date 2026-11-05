"""
Прикладной сервис RentalProcess — оркестрация бизнес-процесса аренды самоката.
Связывает BPMN-схему с доменной моделью. Не содержит бизнес-правил,
а лишь координирует вызовы агрегатов, репозиториев и внешних портов.
Каждой задаче схемы соответствует метод сервиса.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from application.predicates import (
    client_has_debt, client_has_no_debt,
    authorization_succeeded, authorization_failed,
    pause_requested, finish_requested,
    zone_allowed, zone_not_allowed,
    charge_succeeded, charge_failed,
    client_has_problem, client_has_no_problem,
)
from domain.exceptions import GatewayUnresolved, EntityNotFound
from domain.ports import Clock, PaymentGateway, ZoneRegistry
from domain.repositories import TripRepository, ScooterRepository, UserRepository
from domain.trip import Trip
from domain.value_objects import Tariff, Location, PREAUTHORIZATION_AMOUNT


class RentalProcess:
    """Прикладной сервис процесса аренды электросамоката.
    Инкапсулирует всю логику оркестрации BPMN-схемы."""

    def __init__(
        self,
        trips: TripRepository,
        scooters: ScooterRepository,
        users: UserRepository,
        clock: Clock,
        payment: PaymentGateway,
        zones: ZoneRegistry,
        tariff: Tariff,
    ):
        self._trips = trips
        self._scooters = scooters
        self._users = users
        self._clock = clock
        self._payment = payment
        self._zones = zones
        self._tariff = tariff

    # =========================================================
    # Задача 1-2: Бронь запрошена → Забронировать самокат
    # =========================================================
    def request_booking(self, scooter_id: UUID, user_id: UUID) -> UUID:
        """Создать поездку в состоянии «Забронирована» и зарезервировать самокат.
        Возвращает trip_id для последующих операций."""
        now = self._clock.now()

        # Загрузка агрегатов
        scooter = self._scooters.get(scooter_id)
        if scooter is None:
            raise EntityNotFound("Scooter", scooter_id)

        user = self._users.get(user_id)
        if user is None:
            raise EntityNotFound("User", user_id)

        # Резервирование самоката (инвариант проверяется внутри Scooter)
        scooter.reserve()
        self._scooters.save(scooter)

        # Создание поездки в начальном состоянии «Забронирована»
        trip_id = UUID(int=hash((scooter_id, user_id, now)) & 0xFFFFFFFFFFFFFFFF)
        trip = Trip(
            trip_id=trip_id,
            scooter_id=scooter_id,
            user_id=user_id,
            created_at=now,
        )
        self._trips.save(trip)

        return trip_id

    # =========================================================
    # Задача 4-5: Проверить задолженность клиента → Есть задолженность?
    # =========================================================
    def check_client_debt(self, trip_id: UUID) -> None:
        """Проверить наличие задолженности у клиента.
        Разрешает шлюз «Есть задолженность?»."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        user = self._users.get(trip.user_id)
        if user is None:
            raise EntityNotFound("User", trip.user_id)

        now = self._clock.now()

        # Разрешение шлюза
        if client_has_debt(user):
            trip.deny_debt(now)
            self._trips.save(trip)
        elif client_has_no_debt(user):
            # Переход к следующей задаче «Авторизовать платёж»
            self.authorize_payment(trip_id)
        else:
            raise GatewayUnresolved("Есть задолженность?")

    # =========================================================
    # Задача 7-8: Авторизовать платёж → Предавторизация прошла?
    # =========================================================
    def authorize_payment(self, trip_id: UUID) -> None:
        """Выполнить предавторизацию платежа на 300 ₽.
        Разрешает шлюз «Предавторизация прошла?»."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()

        # Вызов порта PaymentGateway
        result = self._payment.authorize(trip.user_id, float(PREAUTHORIZATION_AMOUNT))

        # Разрешение шлюза
        if authorization_succeeded(result):
            # Сохраняем идентификатор авторизации (заглушка)
            trip.record_authorization(f"auth_{trip_id}")
            self._trips.save(trip)
            # Переход к параллельному разветвлению
            self._start_parallel_branches(trip_id)
        elif authorization_failed(result):
            trip.deny_payment(now)
            self._trips.save(trip)
        else:
            raise GatewayUnresolved("Предавторизация прошла?")

    # =========================================================
    # Задача 10-13: Параллельное разветвление и слияние
    # =========================================================
    def _start_parallel_branches(self, trip_id: UUID) -> None:
        """Запустить параллельные ветви: разблокировка замка и тарификация.
        В коде выполняются последовательно, агрегат хранит флаги завершения."""
        self.unlock_scooter(trip_id)
        self.start_billing(trip_id)

    def unlock_scooter(self, trip_id: UUID) -> None:
        """Разблокировать замок самоката (ветвь 1 параллельного шлюза)."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        scooter = self._scooters.get(trip.scooter_id)
        if scooter is None:
            raise EntityNotFound("Scooter", trip.scooter_id)

        # Аренда самоката (инвариант заряда проверяется внутри Scooter)
        scooter.rent()
        self._scooters.save(scooter)

        # Фиксация завершения ветви
        trip.mark_lock_released()
        self._trips.save(trip)

        # Попытка перехода к «Начата» (если вторая ветвь тоже завершена)
        self._try_start_trip(trip_id)

    def start_billing(self, trip_id: UUID) -> None:
        """Запустить тарификацию (ветвь 2 параллельного шлюза)."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()
        trip.mark_billing_started(now)
        self._trips.save(trip)

        # Попытка перехода к «Начата» (если первая ветвь тоже завершена)
        self._try_start_trip(trip_id)

    def _try_start_trip(self, trip_id: UUID) -> None:
        """Попытаться перевести поездку в состояние «Начата».
        Переход возможен только после завершения обеих параллельных ветвей."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        # Инвариант параллельного слияния проверяется внутри Trip.start_trip()
        if trip.lock_released and trip.billing_started:
            now = self._clock.now()
            trip.start_trip(now)
            self._trips.save(trip)

    # =========================================================
    # Задача 14: Выполнить поездку (подпроцесс)
    # =========================================================
    def handle_client_request(
        self, trip_id: UUID, message_type: str, photo_ref: str = None
    ) -> None:
        """Обработать запрос клиента в подпроцессе «Выполнить поездку».
        Разрешает шлюз «Запрос клиента?».
        message_type: 'pause' или 'finish'."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()

        # Разрешение шлюза
        if pause_requested(message_type):
            self.pause_trip(trip_id)
        elif finish_requested(message_type):
            self.check_parking_zone(trip_id, photo_ref)
        else:
            raise GatewayUnresolved("Запрос клиента?")

    def pause_trip(self, trip_id: UUID) -> None:
        """Поставить поездку на паузу."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()
        trip.pause(now)
        self._trips.save(trip)

    def resume_trip(self, trip_id: UUID) -> None:
        """Возобновить поездку после паузы."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()
        trip.resume(now)
        self._trips.save(trip)

    # =========================================================
    # Задача П7-П9: Проверить зону парковки → Зона разрешена?
    # =========================================================
    def check_parking_zone(self, trip_id: UUID, photo_ref: str) -> None:
        """Проверить, разрешена ли зона парковки для завершения.
        Разрешает шлюз «Зона разрешена?».
        В реальной системе координаты берутся от GPS самоката;
        здесь передаются параметром для упрощения."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()

        # Заглушка: координаты передаются параметром (в реальности — от GPS)
        # Для демонстрации используем фиктивные координаты
        location = Location(latitude=55.7558, longitude=37.6173)
        result = self._zones.is_allowed(location)

        # Разрешение шлюза
        if zone_allowed(result):
            self.finish_trip(trip_id, photo_ref)
        elif zone_not_allowed(result):
            # Отказ в завершении: состояние не меняется, фиксируется событие
            trip.record_finish_refused(now)
            self._trips.save(trip)
        else:
            raise GatewayUnresolved("Зона разрешена?")

    def finish_trip(self, trip_id: UUID, photo_ref: str) -> None:
        """Завершить поездку в разрешённой зоне."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        scooter = self._scooters.get(trip.scooter_id)
        if scooter is None:
            raise EntityNotFound("Scooter", trip.scooter_id)

        now = self._clock.now()

        # Завершение поездки (инварианты проверяются внутри Trip)
        trip.finish(photo_ref, now)
        self._trips.save(trip)

        # Возврат самоката
        scooter.return_scooter()
        self._scooters.save(scooter)

        # Переход к расчёту стоимости
        self.calculate_trip_cost(trip_id)

    # =========================================================
    # Задача 17-19: Рассчитать стоимость → Списать → Списание прошло?
    # =========================================================
    def calculate_trip_cost(self, trip_id: UUID) -> None:
        """Рассчитать стоимость поездки по тарифу."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        cost = trip.calculate_cost(self._tariff)
        # В реальной системе стоимость сохраняется в БД;
        # здесь передаём в следующий метод напрямую
        self._charge_trip(trip_id, cost.total_rub)

    def _charge_trip(self, trip_id: UUID, amount: Decimal) -> None:
        """Списать стоимость поездки.
        Разрешает шлюз «Списание прошло?»."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()

        # Вызов порта PaymentGateway
        result = self._payment.charge(trip.user_id, float(amount))

        # Разрешение шлюза
        if charge_succeeded(result):
            trip.charge_ok(now)
            self._trips.save(trip)
            # Переход к отправке чека
            self._send_receipt(trip_id)
        elif charge_failed(result):
            trip.charge_fail(now)
            self._trips.save(trip)
            # Переход к фиксации задолженности
            self._record_debt(trip_id, amount)
        else:
            raise GatewayUnresolved("Списание прошло?")

    def _send_receipt(self, trip_id: UUID) -> None:
        """Отправить чек клиенту (доменное событие ReceiptIssued).
        В реальной системе здесь вызов внешнего сервиса уведомлений."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()
        # Доменное событие ReceiptIssued уже добавлено в журнал внутри Trip
        # (можно добавить явный метод, если требуется)
        self._trips.save(trip)

    def _record_debt(self, trip_id: UUID, amount: Decimal) -> None:
        """Зафиксировать задолженность и заблокировать аккаунт."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        user = self._users.get(trip.user_id)
        if user is None:
            raise EntityNotFound("User", trip.user_id)

        # Начисление задолженности (инвариант проверяется внутри User)
        user.add_debt(amount)
        self._users.save(user)

    # =========================================================
    # События таймеров
    # =========================================================
    def on_booking_expired(self, trip_id: UUID) -> None:
        """Событие таймера 10 мин: бронь не использована.
        Вызывается служебным маршрутом POST /internal/tick."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()

        # Проверка: событие допустимо в текущем состоянии
        if "expire_booking" in trip.allowed_events:
            trip.on_booking_expired(now)
            self._trips.save(trip)

            # Освобождение самоката
            scooter = self._scooters.get(trip.scooter_id)
            if scooter is not None:
                try:
                    scooter.release()
                    self._scooters.save(scooter)
                except Exception:
                    pass  # Самокат уже может быть в другом статусе

    def on_trip_too_long(self, trip_id: UUID) -> None:
        """Событие непрерывающего таймера 12 ч: поездка слишком долгая.
        Состояние поездки не меняется, фиксируется доменное событие."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()
        trip.on_trip_too_long(now)
        self._trips.save(trip)

        # Переход к уведомлению оператора
        if trip.operator_notified:
            self._notify_operator(trip_id)

    def _notify_operator(self, trip_id: UUID) -> None:
        """Уведомить оператора о длительной поездке.
        В реальной системе здесь вызов сервиса уведомлений."""
        pass  # Заглушка

    # =========================================================
    # Ветвь оператора (таймер 12 ч → связь с клиентом)
    # =========================================================
    def record_operator_contact(
        self, trip_id: UUID, has_problem: bool, description: str = None
    ) -> None:
        """Зафиксировать факт связи оператора с клиентом.
        Разрешает шлюз «Есть проблема у клиента?».
        Задача пользователя: оператор принимает результат разговора."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()
        trip.record_operator_contact(has_problem, now)

        # Разрешение шлюза
        if client_has_problem(has_problem):
            if description is None:
                description = "Проблема не описана"
            trip.open_support_request(description, now)
            self._trips.save(trip)
        elif client_has_no_problem(has_problem):
            self._trips.save(trip)
        else:
            raise GatewayUnresolved("Есть проблема у клиента?")

    def resolve_support_request(self, trip_id: UUID, resolution: str) -> None:
        """Закрыть обращение ответом оператора.
        Задача пользователя: оператор принимает решение по проблеме."""
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Trip", trip_id)

        now = self._clock.now()
        trip.resolve_support_request(resolution, now)
        self._trips.save(trip)

    # =========================================================
    # Служебный метод: обработка тика часов
    # =========================================================
    def on_tick(self) -> None:
        """Обработать тик часов приложения.
        Вызывается служебным маршрутом POST /internal/tick.
        Проверяет истечение таймеров для всех поездок."""
        now = self._clock.now()

        for trip in self._trips.all():
            # Таймер 10 мин (бронь)
            if "expire_booking" in trip.allowed_events:
                trip.on_booking_expired(now)
                self._trips.save(trip)

            # Непрерывающий таймер 12 ч
            if trip.start_time is not None and not trip.operator_notified:
                trip.on_trip_too_long(now)
                self._trips.save(trip)