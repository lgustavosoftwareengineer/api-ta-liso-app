from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user_settings import UserSettings
from app.schemas.transaction import TransactionCreate, TransactionUpdate


async def list_transactions(db: AsyncSession, user_id: str) -> list[Transaction]:
    result = await db.execute(
        select(Transaction).where(Transaction.user_id == user_id)
    )
    return list(result.scalars().all())


async def create_transaction(
    db: AsyncSession, user_id: str, data: TransactionCreate
) -> Transaction:
    if data.category_id is not None:
        cat_result = await db.execute(
            select(Category).where(Category.id == data.category_id, Category.user_id == user_id)
        )
        category = cat_result.scalar_one_or_none()
        if category is None:
            raise LookupError("Categoria não encontrada")

        if category.current_balance < data.amount:
            settings_result = await db.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            user_settings = settings_result.scalar_one_or_none()
            if user_settings and user_settings.block_negative_balance:
                raise ValueError(
                    f"Saldo insuficiente. Disponível: {category.current_balance}, solicitado: {data.amount}"
                )

        category.current_balance -= data.amount

    transaction = Transaction(
        user_id=user_id,
        category_id=data.category_id,
        description=data.description,
        amount=data.amount,
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return transaction


async def update_transaction(
    db: AsyncSession, user_id: str, transaction_id: str, data: TransactionUpdate
) -> Transaction | None:
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        return None

    old_amount: Decimal = transaction.amount
    old_category_id: str | None = transaction.category_id

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)

    new_amount: Decimal = transaction.amount
    new_category_id: str | None = transaction.category_id

    if old_category_id == new_category_id:
        if old_amount != new_amount and old_category_id is not None:
            cat_result = await db.execute(select(Category).where(Category.id == old_category_id))
            category = cat_result.scalar_one_or_none()
            if category is not None:
                category.current_balance += old_amount - new_amount
    else:
        if old_category_id is not None:
            cat_result = await db.execute(select(Category).where(Category.id == old_category_id))
            old_category = cat_result.scalar_one_or_none()
            if old_category is not None:
                old_category.current_balance += old_amount
        if new_category_id is not None:
            cat_result = await db.execute(select(Category).where(Category.id == new_category_id))
            new_category = cat_result.scalar_one_or_none()
            if new_category is not None:
                new_category.current_balance -= new_amount

    await db.commit()
    await db.refresh(transaction)
    return transaction


async def delete_transaction(
    db: AsyncSession, user_id: str, transaction_id: str
) -> bool:
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        return False

    if transaction.category_id is not None:
        cat_result = await db.execute(select(Category).where(Category.id == transaction.category_id))
        category = cat_result.scalar_one_or_none()
        if category is not None:
            category.current_balance += transaction.amount

    await db.delete(transaction)
    await db.commit()
    return True
