"""
Testes do Monthly Reset Service — BDD: Reset mensal automático,
snapshot do mês anterior em category_monthly_snapshots, reset de current_balance.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.category import Category
from app.models.category_monthly_snapshot import CategoryMonthlySnapshot
from app.models.transaction import Transaction
from app.models.user_settings import UserSettings
from app.schemas.category import CategoryCreate
from app.services import categories as category_service
from app.services.monthly_reset_service import ensure_monthly_reset
from app.services.user_service import create_user_with_settings


def _mar_2025():
    return datetime(2025, 3, 15, 10, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
class TestMonthlyResetService:
    """Cenários para lazy reset e snapshot."""

    async def test_does_nothing_when_monthly_reset_disabled(self, db_session):
        """Sem reset quando a configuração 'Reset mensal automático' está desativada."""
        user = await create_user_with_settings(db_session, "noreset@example.com")
        result = await db_session.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        settings = result.scalar_one_or_none()
        settings.monthly_reset = False
        await db_session.commit()

        await category_service.create_category(
            db_session,
            user.id,
            CategoryCreate(name="Teste", icon="📁", initial_amount=Decimal("500.00")),
        )
        await db_session.commit()

        result = await db_session.execute(select(Category).where(Category.user_id == user.id))
        cat = result.scalar_one()
        cat.reset_month = 2
        cat.reset_year = 2025
        await db_session.commit()

        await ensure_monthly_reset(db_session, user.id, now=_mar_2025())

        await db_session.refresh(cat)
        assert cat.reset_month == 2
        assert cat.reset_year == 2025
        result = await db_session.execute(select(CategoryMonthlySnapshot))
        assert result.scalar_one_or_none() is None

    async def test_does_nothing_when_no_categories(self, db_session):
        """Não faz nada quando o usuário não tem categorias."""
        user = await create_user_with_settings(db_session, "nocat@example.com")
        await ensure_monthly_reset(db_session, user.id, now=_mar_2025())
        result = await db_session.execute(select(CategoryMonthlySnapshot))
        assert result.scalar_one_or_none() is None

    async def test_does_nothing_when_already_reset_this_month(self, db_session):
        """Não reseta de novo se as categorias já estão no mês atual."""
        user = await create_user_with_settings(db_session, "alreadydone@example.com")
        await category_service.create_category(
            db_session,
            user.id,
            CategoryCreate(name="A", icon="📁", initial_amount=Decimal("100.00")),
        )
        await db_session.commit()
        result = await db_session.execute(select(Category).where(Category.user_id == user.id))
        cat = result.scalar_one()
        cat.reset_month = 3
        cat.reset_year = 2025
        await db_session.commit()

        await ensure_monthly_reset(db_session, user.id, now=_mar_2025())

        result = await db_session.execute(select(CategoryMonthlySnapshot))
        assert result.scalar_one_or_none() is None
        await db_session.refresh(cat)
        assert cat.reset_month == 3
        assert cat.reset_year == 2025

    async def test_creates_snapshots_and_resets_balances_on_first_access_new_month(
        self, db_session
    ):
        """No primeiro acesso do novo mês: salva snapshot do mês anterior e reseta saldos."""
        user = await create_user_with_settings(db_session, "resetme@example.com")
        await category_service.create_category(
            db_session,
            user.id,
            CategoryCreate(name="Alimentação", icon="🛒", initial_amount=Decimal("1000.00")),
        )
        await db_session.commit()
        result = await db_session.execute(select(Category).where(Category.user_id == user.id))
        cat = result.scalar_one()
        cat.current_balance = Decimal("300.00")  # gastou 700
        cat.reset_month = 2
        cat.reset_year = 2025
        await db_session.commit()

        await ensure_monthly_reset(db_session, user.id, now=_mar_2025())

        await db_session.refresh(cat)
        assert cat.current_balance == Decimal("1000.00")
        assert cat.reset_month == 3
        assert cat.reset_year == 2025

        result = await db_session.execute(
            select(CategoryMonthlySnapshot).where(CategoryMonthlySnapshot.category_id == cat.id)
        )
        snapshot = result.scalar_one()
        assert snapshot.month == 2
        assert snapshot.year == 2025
        assert snapshot.initial_amount == Decimal("1000.00")
        assert snapshot.final_balance == Decimal("300.00")

    async def test_snapshot_total_spent_from_previous_month_transactions(self, db_session):
        """total_spent no snapshot é a soma das transações do mês anterior."""
        user = await create_user_with_settings(db_session, "spent@example.com")
        await category_service.create_category(
            db_session,
            user.id,
            CategoryCreate(name="Lazer", icon="🎉", initial_amount=Decimal("500.00")),
        )
        await db_session.commit()
        result = await db_session.execute(select(Category).where(Category.user_id == user.id))
        cat = result.scalar_one()
        cat.reset_month = 2
        cat.reset_year = 2025
        cat.current_balance = Decimal("200.00")  # gastou 300
        await db_session.commit()

        # Transação em fevereiro/2025
        tx = Transaction(
            user_id=user.id,
            category_id=cat.id,
            description="Cinema",
            amount=Decimal("150.00"),
            created_at=datetime(2025, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(tx)
        tx2 = Transaction(
            user_id=user.id,
            category_id=cat.id,
            description="Restaurante",
            amount=Decimal("150.00"),
            created_at=datetime(2025, 2, 20, 12, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(tx2)
        await db_session.commit()

        await ensure_monthly_reset(db_session, user.id, now=_mar_2025())

        result = await db_session.execute(
            select(CategoryMonthlySnapshot).where(CategoryMonthlySnapshot.category_id == cat.id)
        )
        snapshot = result.scalar_one()
        assert snapshot.total_spent == Decimal("300.00")
        assert snapshot.final_balance == Decimal("200.00")

    async def test_resets_categories_with_none_reset_month_year(self, db_session):
        """Categorias que nunca foram resetadas (reset_month/Year None) são resetadas."""
        user = await create_user_with_settings(db_session, "newuser@example.com")
        await category_service.create_category(
            db_session,
            user.id,
            CategoryCreate(name="Nova", icon="📁", initial_amount=Decimal("200.00")),
        )
        await db_session.commit()
        result = await db_session.execute(select(Category).where(Category.user_id == user.id))
        cat = result.scalar_one()
        # Simula categoria antiga/legada sem reset (create_category agora preenche month/year)
        cat.reset_month = None
        cat.reset_year = None
        await db_session.commit()

        await ensure_monthly_reset(db_session, user.id, now=_mar_2025())

        await db_session.refresh(cat)
        assert cat.reset_month == 3
        assert cat.reset_year == 2025
        assert cat.current_balance == Decimal("200.00")
        result = await db_session.execute(
            select(CategoryMonthlySnapshot).where(CategoryMonthlySnapshot.category_id == cat.id)
        )
        snapshot = result.scalar_one()
        assert snapshot.month == 2
        assert snapshot.year == 2025
