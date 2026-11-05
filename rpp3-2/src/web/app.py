"""
Создание Flask-приложения с инициализацией зависимостей.
Доменный и прикладной слои не импортируют Flask — вся связь через этот модуль.
"""
import os
from decimal import Decimal

from flask import Flask

from application.services import RentalProcess
from domain.value_objects import Tariff
from infrastructure.adapters import InMemoryPaymentGateway, InMemoryZoneRegistry
from infrastructure.clocks import ShiftedClock
from infrastructure.repositories import (
    InMemoryUserRepository,
    InMemoryScooterRepository,
    InMemoryTripRepository,
)
from web.errors import register_error_handlers
from web.routes import trips_bp, scooters_bp, users_bp, internal_bp


def create_app() -> Flask:
    """Создать и настроить Flask-приложение."""
    app = Flask(__name__)
    
    # Чтение конфигурации из переменных окружения
    port = int(os.environ.get("PORT", 5000))
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    
    app.config["PORT"] = port
    app.config["LOG_LEVEL"] = log_level
    
    # Создание зависимостей (один раз при запуске)
    user_repo = InMemoryUserRepository()
    scooter_repo = InMemoryScooterRepository()
    trip_repo = InMemoryTripRepository()
    
    clock = ShiftedClock()
    
    payment = InMemoryPaymentGateway(
        authorize_success=True,
        charge_success=True,
    )
    
    from domain.value_objects import Location
    zones = InMemoryZoneRegistry(
        allowed_zones=[
            Location(latitude=55.7558, longitude=37.6173),
        ]
    )
    
    tariff = Tariff(
        per_minute_rub=Decimal("10"),
        per_pause_minute_rub=Decimal("3"),
        min_trip_cost_rub=Decimal("50"),
    )
    
    # Создание прикладного сервиса
    process = RentalProcess(
        trips=trip_repo,
        scooters=scooter_repo,
        users=user_repo,
        clock=clock,
        payment=payment,
        zones=zones,
        tariff=tariff,
    )
    
    # Привязка сервисов к Blueprint'ам
    trips_bp.trip_service = process
    scooters_bp.trip_service = process
    users_bp.trip_service = process
    internal_bp.trip_service = process
    internal_bp.clock = clock
    
    # Регистрация Blueprint'ов
    app.register_blueprint(trips_bp)
    app.register_blueprint(scooters_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(internal_bp)
    
    # Регистрация обработчиков ошибок
    register_error_handlers(app)
    
    # Маршрут проверки готовности контейнера
    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "healthy"}, 200
    
    return app