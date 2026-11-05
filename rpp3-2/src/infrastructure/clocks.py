"""
Реализация протокола Clock для управления временем в приложении.
Позволяет тестировать таймеры без реального ожидания.
"""
from datetime import datetime, timedelta

from domain.exceptions import ClockMovedBack
from domain.ports import Clock


class SystemClock:
    """Реальные системные часы. Используются в продакшене."""

    def now(self) -> datetime:
        return datetime.now()


class ShiftedClock:
    """Часы приложения со сдвигом. Используются для тестирования.
    Показывают системное время + сдвиг, который можно изменить,
    но только вперёд (перевод назад запрещён)."""

    def __init__(self):
        self._offset = timedelta(0)

    def now(self) -> datetime:
        return datetime.now() + self._offset

    def move_to(self, moment: datetime) -> None:
        """Перевести часы на указанный момент.
        Запрещает перевод назад."""
        if moment < self.now():
            raise ClockMovedBack(
                f"Перевод часов назад запрещён: "
                f"текущее время {self.now()}, запрошено {moment}"
            )
        self._offset = moment - datetime.now()

    def move_forward(self, delta: timedelta) -> None:
        """Сдвинуть часы вперёд на указанный интервал."""
        new_time = self.now() + delta
        self.move_to(new_time)


class FixedClock:
    """Фиксированные часы для тестов. Всегда возвращают одно и то же время."""

    def __init__(self, fixed_time: datetime):
        self._fixed_time = fixed_time

    def now(self) -> datetime:
        return self._fixed_time

    def set_time(self, new_time: datetime) -> None:
        """Изменить фиксированное время (для тестов)."""
        self._fixed_time = new_time