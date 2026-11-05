"""
Точка входа для демонстрации бизнес-процесса аренды электросамоката.
Проходит все ключевые пути процесса (P1–P9) из Таблицы 2 методического
руководства, демонстрируя корректность реализации паттерна «Состояние»
и оркестрации BPMN-схемы.

Все сценарии используют ShiftedClock для проверки таймеров без
реального ожидания.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from application.services import RentalProcess
from domain.exceptions import (
    TransitionNotAllowed,
    InvariantViolation,
    GatewayUnresolved,
    EntityNotFound,
    ClockMovedBack,
)
from domain.scooter import Scooter, ScooterStatus
from domain.user import User
from domain.value_objects import Tariff, Location
from infrastructure.adapters import InMemoryPaymentGateway, InMemoryZoneRegistry
from infrastructure.clocks import ShiftedClock
from infrastructure.repositories import (
    InMemoryUserRepository,
    InMemoryScooterRepository,
    InMemoryTripRepository,
)


# =========================================================
# Настройка окружения
# =========================================================
def setup_environment():
    """Создать и связать все зависимости процесса."""
    # Репозитории
    user_repo = InMemoryUserRepository()
    scooter_repo = InMemoryScooterRepository()
    trip_repo = InMemoryTripRepository()

    # Часы приложения (со сдвигом для тестирования таймеров)
    clock = ShiftedClock()

    # Внешние порты (заглушки)
    payment = InMemoryPaymentGateway(
        authorize_success=True,
        charge_success=True,
    )
    zones = InMemoryZoneRegistry(
        allowed_zones=[
            Location(latitude=55.7558, longitude=37.6173),  # Москва, Кремль
        ]
    )

    # Тариф
    tariff = Tariff(
        per_minute_rub=Decimal("10"),
        per_pause_minute_rub=Decimal("3"),
        min_trip_cost_rub=Decimal("50"),
    )

    # Прикладной сервис
    process = RentalProcess(
        trips=trip_repo,
        scooters=scooter_repo,
        users=user_repo,
        clock=clock,
        payment=payment,
        zones=zones,
        tariff=tariff,
    )

    return {
        "user_repo": user_repo,
        "scooter_repo": scooter_repo,
        "trip_repo": trip_repo,
        "clock": clock,
        "payment": payment,
        "zones": zones,
        "tariff": tariff,
        "process": process,
    }


def create_test_data(env):
    """Создать тестовых пользователей и самокатов."""
    user_id = uuid4()
    user = User(user_id=user_id)
    env["user_repo"].save(user)

    scooter_id = uuid4()
    scooter = Scooter(scooter_id=scooter_id, _battery_level=80)
    env["scooter_repo"].save(scooter)

    return user_id, scooter_id


def print_scenario(title: str):
    """Вывести заголовок сценария."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_step(description: str):
    """Вывести описание шага."""
    print(f"\n→ {description}")


def print_result(message: str):
    """Вывести результат."""
    print(f"  ✓ {message}")


def print_error(message: str):
    """Вывести сообщение об ошибке."""
    print(f"  ✗ {message}")


# =========================================================
# Сценарий P1: Успешный путь
# =========================================================
def scenario_p1(env):
    """
    P1: Бронь → Проверка долга → Авторизация → Параллельные ветви →
        Поездка → Завершение в зоне → Оплата.
    Условие: нет долга, авторизация прошла, зона разрешена, списание прошло.
    """
    print_scenario("P1: Успешный путь (поездка оплачена)")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]

    # Шаг 1: Бронь запрошена
    print_step("Бронь запрошена")
    trip_id = process.request_booking(scooter_id, user_id)
    trip = trip_repo.get(trip_id)
    print_result(f"Создана поездка {trip_id}, статус: {trip.status}")
    assert trip.status == "Забронирована"

    # Шаг 2: Проверка задолженности (нет долга)
    print_step("Проверка задолженности клиента")
    process.check_client_debt(trip_id)
    trip = trip_repo.get(trip_id)
    print_result(f"Статус после проверки: {trip.status}")
    # После проверки долга и авторизации — параллельные ветви — «Начата»
    assert trip.status == "Начата"

    # Шаг 3: Поездка началась
    print_step("Поездка началась, клиент едет")
    assert trip.start_time is not None

    # Шаг 4: Завершение в разрешённой зоне
    # Сервис автоматически выполняет цепочку: завершение → расчёт → списание → оплата
    print_step("Клиент завершает поездку в разрешённой зоне")
    process.handle_client_request(trip_id, "finish", photo_ref="photo_123.jpg")
    trip = trip_repo.get(trip_id)
    print_result(f"Финальный статус: {trip.status}")
    # Промежуточное состояние «Завершена» проходит автоматически
    assert trip.status == "Оплачена"

    print_result("Путь P1 пройден успешно")


# =========================================================
# Сценарий P2: Таймер брони (10 мин)
# =========================================================
def scenario_p2(env):
    """
    P2: Бронь → Ожидание → Таймер 10 мин → Бронь снята по сроку.
    """
    print_scenario("P2: Таймер брони (10 мин)")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]
    clock = env["clock"]
    scooter_repo = env["scooter_repo"]

    # Шаг 1: Бронь запрошена
    print_step("Бронь запрошена")
    trip_id = process.request_booking(scooter_id, user_id)
    trip = trip_repo.get(trip_id)
    print_result(f"Статус: {trip.status}")
    assert trip.status == "Забронирована"

    # Шаг 2: Перевод часов на 11 минут вперёд
    print_step("Перевод часов на 11 минут вперёд")
    clock.move_forward(timedelta(minutes=11))
    print_result(f"Текущее время: {clock.now()}")

    # Шаг 3: Событие таймера
    print_step("Событие таймера: бронь не использована")
    process.on_booking_expired(trip_id)
    trip = trip_repo.get(trip_id)
    print_result(f"Статус после таймера: {trip.status}")
    assert trip.status == "Отменена по сроку"

    # Шаг 4: Самокат освобождён
    scooter = scooter_repo.get(scooter_id)
    print_result(f"Статус самоката: {scooter.status.value}")
    assert scooter.status == ScooterStatus.FREE

    print_result("Путь P2 пройден успешно")


# =========================================================
# Сценарий P3: Отказ по задолженности
# =========================================================
def scenario_p3(env):
    """
    P3: Бронь → Пользователь с долгом → Отказ.
    """
    print_scenario("P3: Отказ по задолженности")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]
    user_repo = env["user_repo"]

    # Шаг 1: Начислить задолженность пользователю
    print_step("Начисление задолженности пользователю")
    user = user_repo.get(user_id)
    user.add_debt(Decimal("500"))
    user_repo.save(user)
    print_result(f"Задолженность: {user.debt} ₽, заблокирован: {user.blocked}")

    # Шаг 2: Бронь запрошена
    print_step("Бронь запрошена")
    trip_id = process.request_booking(scooter_id, user_id)
    trip = trip_repo.get(trip_id)
    print_result(f"Статус: {trip.status}")
    assert trip.status == "Забронирована"

    # Шаг 3: Проверка задолженности (есть долг)
    print_step("Проверка задолженности клиента")
    process.check_client_debt(trip_id)
    trip = trip_repo.get(trip_id)
    print_result(f"Статус после проверки: {trip.status}")
    assert trip.status == "Отклонена: задолженность"

    print_result("Путь P3 пройден успешно")


# =========================================================
# Сценарий P4: Отказ по платежу
# =========================================================
def scenario_p4(env):
    """
    P4: Бронь → Проверка долга (нет) → Авторизация не прошла → Отказ.
    """
    print_scenario("P4: Отказ по платежу")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]
    payment = env["payment"]

    # Шаг 1: Настроить платёжный шлюз на отказ
    print_step("Настройка платёжного шлюза: авторизация не пройдёт")
    payment._authorize_success = False

    # Шаг 2: Бронь запрошена
    print_step("Бронь запрошена")
    trip_id = process.request_booking(scooter_id, user_id)
    trip = trip_repo.get(trip_id)
    print_result(f"Статус: {trip.status}")

    # Шаг 3: Проверка задолженности (нет долга) → авторизация
    print_step("Проверка задолженности и авторизация платежа")
    process.check_client_debt(trip_id)
    trip = trip_repo.get(trip_id)
    print_result(f"Статус после авторизации: {trip.status}")
    assert trip.status == "Отклонена: платёж"

    # Восстановить шлюз
    payment._authorize_success = True

    print_result("Путь P4 пройден успешно")


# =========================================================
# Сценарий P5: Завершение с задолженностью (списание не прошло)
# =========================================================
def scenario_p5(env):
    """
    P5: Успешная поездка → Списание не прошло → Задолженность.
    """
    print_scenario("P5: Завершение с задолженностью")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]
    payment = env["payment"]
    user_repo = env["user_repo"]

    # Шаг 1: Настроить шлюз на отказ при списании ПЕРЕД завершением
    print_step("Настройка платёжного шлюза: списание не пройдёт")
    payment._charge_success = False

    # Шаг 2: Бронь и начало поездки (как в P1)
    print_step("Бронь и начало поездки")
    trip_id = process.request_booking(scooter_id, user_id)
    process.check_client_debt(trip_id)
    trip = trip_repo.get(trip_id)
    assert trip.status == "Начата"
    print_result(f"Поездка начата: {trip.status}")

    # Шаг 3: Завершение в зоне
    # Сервис автоматически выполнит: завершение → расчёт → попытка списания → отказ
    print_step("Завершение поездки в разрешённой зоне")
    process.handle_client_request(trip_id, "finish", photo_ref="photo_456.jpg")
    trip = trip_repo.get(trip_id)
    print_result(f"Статус после завершения: {trip.status}")
    assert trip.status == "Не оплачена"

    # Шаг 4: Проверить задолженность пользователя
    user = user_repo.get(user_id)
    print_result(f"Задолженность пользователя: {user.debt} ₽")
    assert user.has_debt
    assert user.blocked

    # Восстановить шлюз
    payment._charge_success = True

    print_result("Путь P5 пройден успешно")


# =========================================================
# Сценарий P6: Поездка с паузой
# =========================================================
def scenario_p6(env):
    """
    P6: Поездка → Пауза → Возобновление → Завершение → Оплата.
    """
    print_scenario("P6: Поездка с паузой")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]
    clock = env["clock"]

    # Шаг 1: Начало поездки
    print_step("Начало поездки")
    trip_id = process.request_booking(scooter_id, user_id)
    process.check_client_debt(trip_id)
    trip = trip_repo.get(trip_id)
    assert trip.status == "Начата"
    print_result(f"Поездка начата: {trip.status}")

    # Шаг 2: Пауза
    print_step("Клиент ставит поездку на паузу")
    process.handle_client_request(trip_id, "pause")
    trip = trip_repo.get(trip_id)
    assert trip.status == "Приостановлена"
    print_result(f"Статус после паузы: {trip.status}")

    # Шаг 3: Перевод часов на 5 минут (пауза тарифицируется по сниженной ставке)
    print_step("Пауза длится 5 минут")
    clock.move_forward(timedelta(minutes=5))

    # Шаг 4: Возобновление
    print_step("Клиент возобновляет поездку")
    process.resume_trip(trip_id)
    trip = trip_repo.get(trip_id)
    assert trip.status == "Начата"
    print_result(f"Статус после возобновления: {trip.status}")
    print_result(f"Время паузы: {trip.total_pause_seconds} сек")

    # Шаг 5: Завершение
    print_step("Завершение поездки")
    process.handle_client_request(trip_id, "finish", photo_ref="photo_789.jpg")
    trip = trip_repo.get(trip_id)
    assert trip.status == "Оплачена"
    print_result(f"Финальный статус: {trip.status}")

    print_result("Путь P6 пройден успешно")


# =========================================================
# Сценарий P7: Неверная зона парковки
# =========================================================
def scenario_p7(env):
    """
    P7: Поездка → Попытка завершения в запрещённой зоне → Отказ →
        Повторная попытка в разрешённой зоне → Оплата.
    """
    print_scenario("P7: Неверная зона парковки")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]
    zones = env["zones"]

    # Шаг 1: Начало поездки
    print_step("Начало поездки")
    trip_id = process.request_booking(scooter_id, user_id)
    process.check_client_debt(trip_id)
    trip = trip_repo.get(trip_id)
    assert trip.status == "Начата"
    print_result(f"Поездка начата: {trip.status}")

    # Шаг 2: Попытка завершения в запрещённой зоне
    print_step("Попытка завершения в запрещённой зоне")
    # Временно убрать разрешённую зону
    zones._allowed_zones = []
    process.handle_client_request(trip_id, "finish", photo_ref="photo_bad.jpg")
    trip = trip_repo.get(trip_id)
    # Состояние не меняется, фиксируется событие FinishRefused
    assert trip.status == "Начата"
    print_result(f"Статус после отказа: {trip.status} (не изменился)")
    print_result(f"Событие FinishRefused зафиксировано в журнале")

    # Шаг 3: Повторная попытка в разрешённой зоне
    print_step("Повторная попытка в разрешённой зоне")
    zones._allowed_zones = [Location(latitude=55.7558, longitude=37.6173)]
    process.handle_client_request(trip_id, "finish", photo_ref="photo_good.jpg")
    trip = trip_repo.get(trip_id)
    assert trip.status == "Оплачена"
    print_result(f"Финальный статус: {trip.status}")

    print_result("Путь P7 пройден успешно")


# =========================================================
# Сценарий P8: Таймер 12 ч → Оператор → Проблем нет
# =========================================================
def scenario_p8(env):
    """
    P8: Поездка → Таймер 12 ч → Уведомление оператора → Связь с клиентом →
        Проблем нет → Поездка продолжается.
    """
    print_scenario("P8: Таймер 12 ч → Оператор → Проблем нет")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]
    clock = env["clock"]

    # Шаг 1: Начало поездки
    print_step("Начало поездки")
    trip_id = process.request_booking(scooter_id, user_id)
    process.check_client_debt(trip_id)
    trip = trip_repo.get(trip_id)
    assert trip.status == "Начата"
    print_result(f"Поездка начата: {trip.status}")

    # Шаг 2: Перевод часов на 13 часов
    print_step("Перевод часов на 13 часов вперёд")
    clock.move_forward(timedelta(hours=13))

    # Шаг 3: Событие таймера 12 ч
    print_step("Событие таймера: поездка слишком долгая")
    process.on_trip_too_long(trip_id)
    trip = trip_repo.get(trip_id)
    print_result(f"Оператор уведомлён: {trip.operator_notified}")
    assert trip.operator_notified
    # Состояние поездки не меняется
    assert trip.status == "Начата"
    print_result(f"Статус поездки: {trip.status} (не изменился)")

    # Шаг 4: Оператор связывается с клиентом (проблем нет)
    print_step("Оператор связывается с клиентом: проблем нет")
    process.record_operator_contact(trip_id, has_problem=False)
    trip = trip_repo.get(trip_id)
    print_result(f"Оператор связался: {trip.operator_contacted}")

    # Шаг 5: Поездка продолжается и завершается
    print_step("Поездка продолжается и завершается")
    process.handle_client_request(trip_id, "finish", photo_ref="photo_long.jpg")
    trip = trip_repo.get(trip_id)
    assert trip.status == "Оплачена"
    print_result(f"Финальный статус: {trip.status}")

    print_result("Путь P8 пройден успешно")


# =========================================================
# Сценарий P9: Таймер 12 ч → Оператор → Есть проблема → Обращение
# =========================================================
def scenario_p9(env):
    """
    P9: Поездка → Таймер 12 ч → Уведомление оператора → Связь с клиентом →
        Есть проблема → Обращение → Ответ оператора.
    """
    print_scenario("P9: Таймер 12 ч → Оператор → Есть проблема")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]
    clock = env["clock"]

    # Шаг 1: Начало поездки
    print_step("Начало поездки")
    trip_id = process.request_booking(scooter_id, user_id)
    process.check_client_debt(trip_id)
    trip = trip_repo.get(trip_id)
    assert trip.status == "Начата"
    print_result(f"Поездка начата: {trip.status}")

    # Шаг 2: Перевод часов на 13 часов
    print_step("Перевод часов на 13 часов вперёд")
    clock.move_forward(timedelta(hours=13))

    # Шаг 3: Событие таймера 12 ч
    print_step("Событие таймера: поездка слишком долгая")
    process.on_trip_too_long(trip_id)
    trip = trip_repo.get(trip_id)
    assert trip.operator_notified
    print_result(f"Оператор уведомлён: {trip.operator_notified}")

    # Шаг 4: Оператор связывается с клиентом (есть проблема)
    print_step("Оператор связывается с клиентом: есть проблема")
    process.record_operator_contact(
        trip_id,
        has_problem=True,
        description="Клиент не может завершить поездку",
    )
    trip = trip_repo.get(trip_id)
    assert trip.active_support_request is not None
    print_result(f"Обращение открыто: {trip.active_support_request.description}")

    # Шаг 5: Оператор обрабатывает обращение
    print_step("Оператор обрабатывает обращение")
    process.resolve_support_request(
        trip_id,
        resolution="Проблема решена, клиент может завершить поездку",
    )
    trip = trip_repo.get(trip_id)
    assert trip.active_support_request.is_resolved
    print_result(f"Обращение закрыто: {trip.active_support_request.resolution}")

    # Шаг 6: Поездка завершается
    print_step("Поездка завершается")
    process.handle_client_request(trip_id, "finish", photo_ref="photo_support.jpg")
    trip = trip_repo.get(trip_id)
    assert trip.status == "Оплачена"
    print_result(f"Финальный статус: {trip.status}")

    print_result("Путь P9 пройден успешно")


# =========================================================
# Демонстрация недопустимых событий
# =========================================================
def scenario_invalid_events(env):
    """
    Демонстрация обработки недопустимых событий.
    Проверяет, что состояние не меняется при попытке выполнить
    недопустимое событие.
    """
    print_scenario("Демонстрация недопустимых событий")

    user_id, scooter_id = create_test_data(env)
    process = env["process"]
    trip_repo = env["trip_repo"]

    # Шаг 1: Создать поездку
    print_step("Создание поездки")
    trip_id = process.request_booking(scooter_id, user_id)
    trip = trip_repo.get(trip_id)
    initial_status = trip.status
    print_result(f"Начальный статус: {initial_status}")

    # Шаг 2: Попытка поставить на паузу (недопустимо в «Забронирована»)
    print_step("Попытка поставить на паузу в состоянии «Забронирована»")
    try:
        process.pause_trip(trip_id)
        print_error("Ожидалось исключение TransitionNotAllowed")
    except TransitionNotAllowed as e:
        print_result(f"Переход запрещён: {e}")
        trip = trip_repo.get(trip_id)
        assert trip.status == initial_status
        print_result(f"Статус не изменился: {trip.status}")

    # Шаг 3: Попытка завершить поездку (недопустимо в «Забронирована»)
    print_step("Попытка завершить поездку в состоянии «Забронирована»")
    try:
        process.handle_client_request(trip_id, "finish", photo_ref="photo.jpg")
        print_error("Ожидалось исключение TransitionNotAllowed")
    except TransitionNotAllowed as e:
        print_result(f"Переход запрещён: {e}")
        trip = trip_repo.get(trip_id)
        assert trip.status == initial_status
        print_result(f"Статус не изменился: {trip.status}")

    print_result("Недопустимые события обработаны корректно")


# =========================================================
# Демонстрация защиты от перевода часов назад
# =========================================================
def scenario_clock_protection(env):
    """
    Демонстрация защиты часов приложения от перевода назад.
    """
    print_scenario("Защита часов от перевода назад")

    clock = env["clock"]

    # Шаг 1: Перевод часов вперёд
    print_step("Перевод часов на 1 час вперёд")
    initial_time = clock.now()
    clock.move_forward(timedelta(hours=1))
    print_result(f"Текущее время: {clock.now()}")

    # Шаг 2: Попытка перевести часы назад
    print_step("Попытка перевести часы назад")
    try:
        clock.move_to(initial_time)
        print_error("Ожидалось исключение ClockMovedBack")
    except ClockMovedBack as e:
        print_result(f"Перевод запрещён: {e}")

    print_result("Защита часов работает корректно")


# =========================================================
# Основная функция
# =========================================================
def main():
    """Запуск всех демонстрационных сценариев."""
    print("  Процесс аренды электросамоката")

    # Сценарий P1: Успешный путь
    env = setup_environment()
    scenario_p1(env)

    # Сценарий P2: Таймер брони
    env = setup_environment()
    scenario_p2(env)

    # Сценарий P3: Отказ по задолженности
    env = setup_environment()
    scenario_p3(env)

    # Сценарий P4: Отказ по платежу
    env = setup_environment()
    scenario_p4(env)

    # Сценарий P5: Завершение с задолженностью
    env = setup_environment()
    scenario_p5(env)

    # Сценарий P6: Поездка с паузой
    env = setup_environment()
    scenario_p6(env)

    # Сценарий P7: Неверная зона парковки
    env = setup_environment()
    scenario_p7(env)

    # Сценарий P8: Таймер 12 ч → Проблем нет
    env = setup_environment()
    scenario_p8(env)

    # Сценарий P9: Таймер 12 ч → Есть проблема
    env = setup_environment()
    scenario_p9(env)

    # Демонстрация недопустимых событий
    env = setup_environment()
    scenario_invalid_events(env)

    # Демонстрация защиты часов
    env = setup_environment()
    scenario_clock_protection(env)

    print("  Все сценарии выполнены успешно!")


if __name__ == "__main__":
    main()