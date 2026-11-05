"""
Инфраструктурные адаптеры (заглушки) для внешних зависимостей.
В реальной системе здесь были бы HTTP-клиенты к платёжному сервису,
GPS-сервису и т.д. Для демонстрации используются In-Memory заглушки.
"""
from uuid import UUID

from domain.ports import PaymentGateway, ZoneRegistry
from domain.value_objects import Location


class InMemoryPaymentGateway:
    """Заглушка платёжного сервиса.
    Поведение настраивается через конструктор."""

    def __init__(self, authorize_success: bool = True, charge_success: bool = True):
        self._authorize_success = authorize_success
        self._charge_success = charge_success

    def authorize(self, user_id: UUID, amount: float) -> bool:
        """Предварительная авторизация (предавторизация) на сумму 300 ₽."""
        return self._authorize_success

    def charge(self, user_id: UUID, amount: float) -> bool:
        """Фактическое списание стоимости поездки."""
        return self._charge_success


class InMemoryZoneRegistry:
    """Заглушка реестра зон парковки.
    Разрешает завершение только в указанных координатах."""

    def __init__(self, allowed_zones: list[Location] = None):
        self._allowed_zones = allowed_zones or [
            Location(latitude=55.7558, longitude=37.6173),  # Москва, Кремль
            Location(latitude=55.7539, longitude=37.6208),  # Москва, Красная площадь
        ]

    def is_allowed(self, location: Location) -> bool:
        """Проверить, разрешено ли завершить поездку в указанной точке."""
        # Простая проверка: координаты должны совпадать с одной из разрешённых зон
        # В реальной системе здесь была бы проверка полигона или радиуса
        for zone in self._allowed_zones:
            if (
                abs(zone.latitude - location.latitude) < 0.001
                and abs(zone.longitude - location.longitude) < 0.001
            ):
                return True
        return False


class MockPaymentGateway:
    """Мок платёжного сервиса для тестов.
    Позволяет динамически менять поведение."""

    def __init__(self):
        self._authorize_result = True
        self._charge_result = True

    def set_authorize_result(self, result: bool) -> None:
        self._authorize_result = result

    def set_charge_result(self, result: bool) -> None:
        self._charge_result = result

    def authorize(self, user_id: UUID, amount: float) -> bool:
        return self._authorize_result

    def charge(self, user_id: UUID, amount: float) -> bool:
        return self._charge_result