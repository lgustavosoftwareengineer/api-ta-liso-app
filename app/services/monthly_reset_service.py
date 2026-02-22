"""
Reset mensal automático (lazy reset): no primeiro acesso do novo mês,
salva snapshot do mês anterior em category_monthly_snapshots e reseta
current_balance das categorias para initial_amount.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.category_monthly_snapshot import CategoryMonthlySnapshot
from app.models.transaction import Transaction
from app.models.user_settings import UserSettings


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return 12, year - 1
    return month - 1, year


async def ensure_monthly_reset(
    db: AsyncSession,
    user_id: str,
    *,
    now: datetime | None = None,
) -> None:
    """
    Se a configuração "Reset mensal automático" estiver ativada e for o primeiro
    acesso do usuário no novo mês, salva snapshots do mês anterior e reseta
    os saldos das categorias.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    current_month = now.month
    current_year = now.year

    # Carrega configuração do usuário
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None or not settings.monthly_reset:
        return

    # Carrega categorias do usuário
    result = await db.execute(
        select(Category).where(Category.user_id == user_id)
    )
    categories = result.scalars().all()
    if not categories:
        return

    # Verifica se precisa resetar: alguma categoria está em mês anterior (ou nunca resetou)
    needs_reset = any(
        cat.reset_year is None
        or cat.reset_month is None
        or (cat.reset_year, cat.reset_month) < (current_year, current_month)
        for cat in categories
    )
    if not needs_reset:
        return

    prev_month, prev_year = _prev_month(current_year, current_month)
    # Limites do mês anterior (UTC) para total_spent
    start_prev = datetime(prev_year, prev_month, 1, tzinfo=timezone.utc)
    if current_month == 1:
        start_curr = datetime(current_year, 1, 1, tzinfo=timezone.utc)
    else:
        start_curr = datetime(current_year, current_month, 1, tzinfo=timezone.utc)

    for category in categories:
        # Total gasto no mês anterior (transações da categoria no período)
        sum_result = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.category_id == category.id,
                Transaction.created_at >= start_prev,
                Transaction.created_at < start_curr,
            )
        )
        total_spent = sum_result.scalar() or Decimal("0")
        if isinstance(total_spent, (int, float)):
            total_spent = Decimal(str(total_spent))

        snapshot = CategoryMonthlySnapshot(
            category_id=category.id,
            month=prev_month,
            year=prev_year,
            initial_amount=category.initial_amount,
            total_spent=total_spent,
            final_balance=category.current_balance,
        )
        db.add(snapshot)

        category.current_balance = category.initial_amount
        category.reset_month = current_month
        category.reset_year = current_year

    await db.commit()
