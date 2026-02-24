from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


async def list_categories(db: AsyncSession, user_id: str) -> list[Category]:
    result = await db.execute(
        select(Category).where(Category.user_id == user_id)
    )
    return list(result.scalars().all())


async def create_category(
    db: AsyncSession, user_id: str, data: CategoryCreate
) -> Category:
    # BDD: nome duplicado não deve ser salvo
    existing = await db.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.name == data.name,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Categoria com o nome '{data.name}' já existe")

    category = Category(
        user_id=user_id,
        name=data.name,
        icon=data.icon,
        initial_amount=data.initial_amount,
        current_balance=data.initial_amount,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession, user_id: str, category_id: str, data: CategoryUpdate
) -> Category | None:
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        return None

    if data.name is not None:
        category.name = data.name
    if data.icon is not None:
        category.icon = data.icon
    if data.initial_amount is not None:
        # BDD: recalcular current_balance proporcionalmente
        diff = data.initial_amount - category.initial_amount
        category.initial_amount = data.initial_amount
        category.current_balance = category.current_balance + diff

    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(
    db: AsyncSession, user_id: str, category_id: str
) -> bool:
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        return False

    await db.delete(category)
    await db.commit()
    return True
