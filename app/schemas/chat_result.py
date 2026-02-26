"""Result type for chat message processing (service layer)."""
from dataclasses import dataclass, field

from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.chat import InsufficientBalanceDetail


@dataclass
class ChatProcessResult:
    reply: str
    action: str | None = None
    transaction: Transaction | None = None
    insufficient_balance: InsufficientBalanceDetail | None = None
    categories: list[Category] = field(default_factory=list)
    category: Category | None = None
    transactions: list[Transaction] = field(default_factory=list)
