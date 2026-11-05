"""
Агрегат User — клиент сервиса проката.
Отвечает за учёт задолженности и блокировку аккаунта.
В ЛР2 агрегат отсутствовал (использовалась только ссылка user_id),
поэтому вводится впервые в Разделе III.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from domain.exceptions import InvariantViolation


@dataclass
class User:
    """Корень агрегата User.
    Инварианты:
    - debt >= 0 (задолженность не может быть отрицательной);
    - если debt > 0, то blocked == True (аккаунт блокируется автоматически).
    """
    user_id: UUID
    _debt: Decimal = field(default=Decimal("0"), repr=False)
    _blocked: bool = field(default=False, repr=False)

    # === Свойства только для чтения ===
    @property
    def debt(self) -> Decimal:
        return self._debt

    @property
    def blocked(self) -> bool:
        return self._blocked

    @property
    def has_debt(self) -> bool:
        """Предикат для шлюза «Есть задолженность?».
        Задолженность считается ненулевой при debt > 0."""
        return self._debt > 0

    # === Доменные методы ===
    def add_debt(self, amount: Decimal) -> None:
        """Начислить задолженность и заблокировать аккаунт.
        Вызывается при неуспешном списании стоимости поездки."""
        if amount <= 0:
            raise InvariantViolation(
                f"Сумма задолженности должна быть положительной, "
                f"получено {amount}"
            )
        self._debt += amount
        # Инвариант: наличие задолженности автоматически блокирует аккаунт
        self._blocked = True

    def pay_debt(self, amount: Decimal) -> None:
        """Погасить задолженность. Снимает блокировку при полном погашении."""
        if amount <= 0:
            raise InvariantViolation(
                f"Сумма платежа должна быть положительной, получено {amount}"
            )
        if amount > self._debt:
            raise InvariantViolation(
                f"Нельзя погасить больше, чем задолженность "
                f"({self._debt} ₽)"
            )
        self._debt -= amount
        if self._debt == 0:
            self._blocked = False

    def block(self) -> None:
        """Принудительная блокировка аккаунта (например, оператором)."""
        self._blocked = True

    def unblock(self) -> None:
        """Разблокировка аккаунта. Допустима только при отсутствии долга."""
        if self._debt > 0:
            raise InvariantViolation(
                "Нельзя разблокировать аккаунт с непогашенной задолженностью"
            )
        self._blocked = False