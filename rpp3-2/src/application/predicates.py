"""
Предикаты для исключающих шлюзов BPMN-схемы.
Каждый предикат — чистая функция, возвращающая bool.
Используются в прикладном сервисе для разрешения шлюзов.
Если ни одно условие не выполнено, сервис выбрасывает GatewayUnresolved.
"""
from domain.user import User
from domain.trip import Trip


# === Шлюз «Есть задолженность?» ===
def client_has_debt(user: User) -> bool:
    """Предикат: у клиента есть непогашенная задолженность."""
    return user.has_debt


def client_has_no_debt(user: User) -> bool:
    """Предикат: у клиента нет задолженности."""
    return not user.has_debt


# === Шлюз «Предавторизация прошла?» ===
def authorization_succeeded(result: bool) -> bool:
    """Предикат: предавторизация платежа успешна."""
    return result is True


def authorization_failed(result: bool) -> bool:
    """Предикат: предавторизация платежа не прошла."""
    return result is False


# === Шлюз «Запрос клиента?» (в подпроцессе «Выполнить поездку») ===
def pause_requested(message_type: str) -> bool:
    """Предикат: клиент запросил паузу."""
    return message_type == "pause"


def finish_requested(message_type: str) -> bool:
    """Предикат: клиент запросил завершение поездки."""
    return message_type == "finish"


# === Шлюз «Зона разрешена?» ===
def zone_allowed(result: bool) -> bool:
    """Предикат: зона парковки разрешена для завершения."""
    return result is True


def zone_not_allowed(result: bool) -> bool:
    """Предикат: зона парковки запрещена."""
    return result is False


# === Шлюз «Списание прошло?» ===
def charge_succeeded(result: bool) -> bool:
    """Предикат: списание стоимости успешно."""
    return result is True


def charge_failed(result: bool) -> bool:
    """Предикат: списание стоимости не прошло."""
    return result is False


# === Шлюз «Есть проблема у клиента?» (ветвь оператора) ===
def client_has_problem(has_problem: bool) -> bool:
    """Предикат: оператор выявил проблему у клиента."""
    return has_problem is True


def client_has_no_problem(has_problem: bool) -> bool:
    """Предикат: проблем у клиента нет."""
    return has_problem is False