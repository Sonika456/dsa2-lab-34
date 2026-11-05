"""
Иерархия доменных исключений.
Разделяет бизнес-ошибки (недопустимое событие, нарушение инварианта,
нерешённый шлюз) от технических сбоев. В веб-слое (Раздел IV) каждое
исключение транслируется в свой HTTP-код ответа.
"""


class DomainError(Exception):
    """Базовый класс всех доменных ошибок."""
    pass


class TransitionNotAllowed(DomainError):
    """Попытка выполнить событие в состоянии, где оно недопустимо.
    В веб-слое -> 409 Conflict."""

    def __init__(self, state: str, event: str):
        super().__init__(
            f"Событие '{event}' недопустимо в состоянии «{state}»"
        )
        self.state = state
        self.event = event


class InvariantViolation(DomainError):
    """Нарушение бизнес-инварианта агрегата или объекта-значения.
    В веб-слое -> 422 Unprocessable Content."""
    pass


class GatewayUnresolved(DomainError):
    """Ни одно условие исключающего шлюза не выполнено,
    а поток по умолчанию отсутствует. Означает ошибку схемы BPMN
    или реализации. В веб-слое -> 500 Internal Server Error."""

    def __init__(self, gateway_name: str):
        super().__init__(
            f"Шлюз «{gateway_name}» не разрешился: "
            f"ни одно условие не выполнено"
        )
        self.gateway_name = gateway_name


class EntityNotFound(DomainError):
    """Агрегат с указанным идентификатором не найден в репозитории.
    В веб-слое -> 404 Not Found."""

    def __init__(self, entity: str, entity_id):
        super().__init__(f"{entity} с id={entity_id} не найден")
        self.entity = entity
        self.entity_id = entity_id


class ClockMovedBack(DomainError):
    """Попытка перевести часы приложения назад.
    В веб-слое -> 422 Unprocessable Content."""
    pass