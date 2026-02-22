"""
Testes do Categories Service — BDD: Gerenciamento de Categorias.
Criar nova categoria (nome, orçamento, ícone), nome duplicado erro, listar, editar, excluir.
"""
from decimal import Decimal

import pytest

from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services import categories as category_service
from app.services.user_service import create_user_with_settings


@pytest.mark.asyncio
class TestCategoriesService:
    """Cenários para CRUD de categorias."""

    async def test_list_categories_empty(self, db_session):
        """Listagem vazia quando usuário não tem categorias."""
        user = await create_user_with_settings(db_session, "cat1@example.com")
        result = await category_service.list_categories(db_session, user.id)
        assert result == []

    async def test_create_category_saves_with_initial_amount_and_balance(self, db_session):
        """Criar nova categoria: current_balance igual ao initial_amount."""
        user = await create_user_with_settings(db_session, "cat2@example.com")
        data = CategoryCreate(
            name="Alimentação",
            icon="🛒",
            initial_amount=Decimal("1000.00"),
        )
        category = await category_service.create_category(db_session, user.id, data)
        assert category.id is not None
        assert category.name == "Alimentação"
        assert category.icon == "🛒"
        assert category.initial_amount == Decimal("1000.00")
        assert category.current_balance == Decimal("1000.00")
        assert category.user_id == user.id

    async def test_create_category_duplicate_name_raises_or_returns_error(self, db_session):
        """Criar categoria com nome duplicado: sistema deve exibir erro e não salvar."""
        user = await create_user_with_settings(db_session, "cat3@example.com")
        data = CategoryCreate(
            name="Transporte",
            icon="🚗",
            initial_amount=Decimal("500.00"),
        )
        await category_service.create_category(db_session, user.id, data)
        # BDD: ao tentar criar outra com mesmo nome, deve falhar
        with pytest.raises(ValueError, match="já existe"):
            await category_service.create_category(db_session, user.id, data)

    async def test_list_categories_returns_created(self, db_session):
        """Listagem exibe a nova categoria."""
        user = await create_user_with_settings(db_session, "cat4@example.com")
        data = CategoryCreate(
            name="Lazer",
            icon="🎉",
            initial_amount=Decimal("300.00"),
        )
        created = await category_service.create_category(db_session, user.id, data)
        listed = await category_service.list_categories(db_session, user.id)
        assert len(listed) == 1
        assert listed[0].id == created.id
        assert listed[0].name == "Lazer"

    async def test_update_category_name_and_icon(self, db_session):
        """Editar nome e ícone de uma categoria."""
        user = await create_user_with_settings(db_session, "cat5@example.com")
        data = CategoryCreate(
            name="Comida",
            icon="🛒",
            initial_amount=Decimal("800.00"),
        )
        category = await category_service.create_category(db_session, user.id, data)
        update_data = CategoryUpdate(name="Feira e Mercado", icon="🥗")
        updated = await category_service.update_category(
            db_session, user.id, category.id, update_data
        )
        assert updated is not None
        assert updated.name == "Feira e Mercado"
        assert updated.icon == "🥗"

    async def test_update_category_initial_amount_recalculates_balance(self, db_session):
        """Editar orçamento: initial_amount atualizado e current_balance proporcional (ou igual)."""
        user = await create_user_with_settings(db_session, "cat6@example.com")
        data = CategoryCreate(
            name="Alimentação",
            icon="🛒",
            initial_amount=Decimal("1000.00"),
        )
        category = await category_service.create_category(db_session, user.id, data)
        update_data = CategoryUpdate(initial_amount=Decimal("1500.00"))
        updated = await category_service.update_category(
            db_session, user.id, category.id, update_data
        )
        assert updated is not None
        assert updated.initial_amount == Decimal("1500.00")
        # BDD: recalcular current_balance proporcionalmente (sem gastos = igual ao initial)
        assert updated.current_balance == Decimal("1500.00")

    async def test_delete_category_removes_category(self, db_session):
        """Excluir categoria sem lançamentos: sistema remove a categoria."""
        user = await create_user_with_settings(db_session, "cat7@example.com")
        data = CategoryCreate(
            name="Teste",
            icon="📁",
            initial_amount=Decimal("100.00"),
        )
        category = await category_service.create_category(db_session, user.id, data)
        deleted = await category_service.delete_category(db_session, user.id, category.id)
        assert deleted is True
        listed = await category_service.list_categories(db_session, user.id)
        assert len(listed) == 0

    async def test_delete_category_returns_false_when_not_found(self, db_session):
        """Excluir categoria inexistente retorna False."""
        user = await create_user_with_settings(db_session, "cat8@example.com")
        deleted = await category_service.delete_category(
            db_session, user.id, "id-inexistente"
        )
        assert deleted is False
