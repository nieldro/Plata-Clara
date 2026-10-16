import datetime as _dt
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Numeric, String, Table,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

Money = Numeric(14, 2)

transaction_tags = Table(
    "transaction_tags", Base.metadata,
    Column("transaction_id", ForeignKey("transactions.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Las sesiones (tokens) emitidas antes de este momento dejan de valer al cambiar la contraseña.
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Account(Base):
    """Cuenta en una entidad: ahorros, corriente, billetera, inversión, tarjeta o efectivo.

    `institution` es el slug del catálogo (institutions.py); si la entidad no está
    listada se guarda el nombre libre en `institution_name`. Una tarjeta de crédito
    queda ligada a una Debt (`debt_id`): sus gastos suben la deuda y los abonos la bajan.
    """
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20), default="savings")
    institution: Mapped[str | None] = mapped_column(String(40), nullable=True)
    institution_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    initial_balance: Mapped[Decimal] = mapped_column(Money, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="COP")
    credit_limit: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    debt_id: Mapped[int | None] = mapped_column(ForeignKey("debts.id"), nullable=True)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(10))  # income | expense


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(10))  # income | expense
    amount: Mapped[Decimal] = mapped_column(Money)
    date: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    # Las dos patas de una transferencia comparten este id; no cuentan como ingreso ni gasto.
    transfer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # Huella del renglón de un extracto importado; evita importar dos veces el mismo movimiento.
    import_hash: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    # Movimiento de un préstamo (prestar o cobrar): mueve el saldo, pero no es gasto ni ingreso del mes.
    loan_id: Mapped[int | None] = mapped_column(ForeignKey("loans.id"), nullable=True, index=True)
    tags: Mapped[list["Tag"]] = relationship(secondary=transaction_tags, lazy="selectin")
    attachments: Mapped[list["Attachment"]] = relationship(lazy="selectin", cascade="all, delete-orphan")

    @property
    def tag_names(self) -> list[str]:
        return sorted(t.name for t in self.tags)

    @property
    def attachment_count(self) -> int:
        return len(self.attachments)


class Attachment(Base):
    """Foto o PDF de un recibo. El archivo vive en disco con un nombre generado (nunca el del usuario)."""
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    filename: Mapped[str] = mapped_column(String(100))  # solo para mostrar
    stored_name: Mapped[str] = mapped_column(String(60))  # uuid + extensión
    content_type: Mapped[str] = mapped_column(String(40))
    size: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Loan(Base):
    """Plata que le prestaste a alguien (lent) o que alguien te prestó (borrowed), sin intereses."""
    __tablename__ = "loans"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    person: Mapped[str] = mapped_column(String(100))
    direction: Mapped[str] = mapped_column(String(10))  # lent = me deben | borrowed = debo
    amount: Mapped[Decimal] = mapped_column(Money)
    date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[_dt.date | None] = mapped_column(Date, nullable=True)  # _dt: el campo «date» de arriba tapa al tipo
    note: Mapped[str] = mapped_column(String(255), default="")


class LoanPayment(Base):
    __tablename__ = "loan_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loans.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    date: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(String(255), default="")
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)


class Tag(Base):
    """Etiqueta libre para seguir un proyecto o tema (viaje-cartagena, regalo-mama...)."""
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(30))


class CategoryRule(Base):
    """Palabra clave → categoría. Se aprende de tus movimientos (hits) o la creas tú (manual)."""
    __tablename__ = "category_rules"
    __table_args__ = (UniqueConstraint("user_id", "keyword", "category_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    keyword: Mapped[str] = mapped_column(String(40), index=True)  # sin tildes y en minúsculas
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    hits: Mapped[int] = mapped_column(default=1)
    manual: Mapped[bool] = mapped_column(Boolean, default=False)


class Debt(Base):
    """Tarjeta de crédito o crédito (libre inversión, vehículo, hipotecario...)."""
    __tablename__ = "debts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))  # credit_card | loan
    original_amount: Mapped[Decimal] = mapped_column(Money)
    current_balance: Mapped[Decimal] = mapped_column(Money)
    rate: Mapped[Decimal] = mapped_column(Numeric(8, 4))  # porcentaje, ej. 28.5
    rate_type: Mapped[str] = mapped_column(String(2), default="EA")  # EA | MV | NA
    term_months: Mapped[int | None] = mapped_column(nullable=True)
    monthly_payment: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    due_day: Mapped[int | None] = mapped_column(nullable=True)


class DebtPayment(Base):
    __tablename__ = "debt_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    interest: Mapped[Decimal] = mapped_column(Money)
    principal: Mapped[Decimal] = mapped_column(Money)
    date: Mapped[date] = mapped_column(Date)


class SavingsGoal(Base):
    __tablename__ = "savings_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    target_amount: Mapped[Decimal] = mapped_column(Money)
    current_amount: Mapped[Decimal] = mapped_column(Money, default=0)
    target_date: Mapped[date] = mapped_column(Date)
    annual_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)  # EA %, ej. CDT/cuenta de ahorro


class SavingsContribution(Base):
    """Aporte (+) o retiro (−) de una meta. El dinero sigue en tus cuentas: la meta solo lo aparta."""
    __tablename__ = "savings_contributions"
    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("savings_goals.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    date: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(String(255), default="")


class Recurring(Base):
    """Movimiento que se repite (arriendo, suscripciones, nómina...)."""
    __tablename__ = "recurring"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(10))  # income | expense
    amount: Mapped[Decimal] = mapped_column(Money)
    note: Mapped[str] = mapped_column(String(255), default="")
    frequency: Mapped[str] = mapped_column(String(10))  # weekly | biweekly | monthly
    anchor_day: Mapped[int] = mapped_column()  # día del mes original (para meses cortos)
    next_date: Mapped[date] = mapped_column(Date, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Notification(Base):
    """Aviso para el usuario. `key` evita repetir el mismo aviso."""
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # budget | due | goal | recurring
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500), default="")
    key: Mapped[str] = mapped_column(String(120))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Budget(Base):
    """Tope mensual de gasto para una categoría."""
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[Decimal] = mapped_column(Money)
