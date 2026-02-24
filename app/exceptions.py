from decimal import Decimal


class InsufficientBalanceError(ValueError):
    def __init__(self, available: Decimal, requested: Decimal) -> None:
        self.available = available
        self.requested = requested
        super().__init__(f"Saldo insuficiente. Disponível: {available}, solicitado: {requested}")
