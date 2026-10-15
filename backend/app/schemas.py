import datetime as _dt  # para campos llamados «date» con valor por defecto (si no, tapan el tipo)
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

RateType = Literal["EA", "MV", "NA"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth ---
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=100)


class UserOut(ORM):
    id: int
    email: EmailStr
    name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- cuentas / categorías / movimientos ---
AccountType = Literal["savings", "checking", "wallet", "investment", "credit_card", "cash"]


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: AccountType = "savings"
    institution: str | None = None  # slug del catálogo
    institution_name: str | None = Field(default=None, max_length=100)  # entidad no listada
    initial_balance: Decimal = Decimal(0)  # en tarjeta: deuda actual
    currency: str = "COP"
    # solo tarjeta de crédito
    credit_limit: Decimal | None = Field(default=None, gt=0)
    rate: Decimal = Field(default=Decimal(0), ge=0)
    rate_type: RateType = "EA"
    monthly_payment: Decimal | None = Field(default=None, gt=0)
    due_day: int | None = Field(default=None, ge=1, le=31)  # día de pago de la tarjeta

    @model_validator(mode="after")
    def _check(self):
        if self.type != "cash" and not self.institution and not (self.institution_name or "").strip():
            raise ValueError("Elige una entidad de la lista o escribe el nombre de la otra entidad")
        if self.type == "credit_card" and self.initial_balance < 0:
            raise ValueError("La deuda actual de la tarjeta no puede ser negativa")
        return self


class AccountOut(ORM):
    id: int
    name: str
    type: AccountType
    institution: str | None
    institution_name: str | None
    currency: str
    initial_balance: Decimal
    credit_limit: Decimal | None
    debt_id: int | None
    balance: Decimal = Decimal(0)  # en tarjeta: -deuda
    available: Decimal | None = None  # en tarjeta: cupo - deuda


class CategoryIn(BaseModel):
    name: str
    kind: Literal["income", "expense"]


class CategoryOut(ORM, CategoryIn):
    id: int


class TransactionIn(BaseModel):
    account_id: int
    category_id: int | None = None
    kind: Literal["income", "expense"]
    amount: Decimal = Field(gt=0)
    date: date
    note: str = ""


class TransactionOut(ORM, TransactionIn):
    id: int
    transfer_id: str | None = None


class TransferIn(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Decimal = Field(gt=0)
    date: date
    note: str = Field(default="", max_length=255)


# --- deudas ---
class DebtIn(BaseModel):
    name: str
    kind: Literal["credit_card", "loan"]
    original_amount: Decimal = Field(gt=0)
    current_balance: Decimal = Field(ge=0)
    rate: Decimal = Field(ge=0)
    rate_type: RateType = "EA"
    term_months: int | None = Field(default=None, gt=0)
    monthly_payment: Decimal | None = Field(default=None, gt=0)
    due_day: int | None = Field(default=None, ge=1, le=31)


class DebtOut(ORM, DebtIn):
    id: int


class DebtPaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    date: date


class DebtPaymentOut(ORM):
    id: int
    amount: Decimal
    interest: Decimal
    principal: Decimal
    date: date


# --- notificaciones ---
class NotificationOut(ORM):
    id: int
    kind: str
    title: str
    body: str
    read: bool
    created_at: datetime


# --- recurrentes ---
class RecurringIn(BaseModel):
    account_id: int
    category_id: int | None = None
    kind: Literal["income", "expense"]
    amount: Decimal = Field(gt=0)
    note: str = Field(default="", max_length=255)
    frequency: Literal["weekly", "biweekly", "monthly"] = "monthly"
    start_date: date  # primera vez que se registra


class RecurringOut(ORM):
    id: int
    account_id: int
    category_id: int | None
    kind: Literal["income", "expense"]
    amount: Decimal
    note: str
    frequency: Literal["weekly", "biweekly", "monthly"]
    next_date: date
    active: bool


# --- presupuestos ---
class BudgetIn(BaseModel):
    amount: Decimal = Field(gt=0)


# --- ahorro ---
class GoalIn(BaseModel):
    name: str
    target_amount: Decimal = Field(gt=0)
    current_amount: Decimal = Field(default=Decimal(0), ge=0)
    target_date: date
    annual_rate: Decimal = Field(default=Decimal(0), ge=0)


class GoalOut(ORM, GoalIn):
    id: int


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    target_amount: Decimal | None = Field(default=None, gt=0)
    target_date: date | None = None
    annual_rate: Decimal | None = Field(default=None, ge=0)


class ContributionIn(BaseModel):
    amount: Decimal = Field(gt=0)
    kind: Literal["deposit", "withdraw"] = "deposit"
    date: _dt.date | None = None  # hoy por defecto
    note: str = Field(default="", max_length=255)


class ContributionOut(ORM):
    id: int
    amount: Decimal  # positivo = aporte, negativo = retiro
    date: date
    note: str


# --- simulador ---
class LoanSimIn(BaseModel):
    amount: float = Field(gt=0)
    rate: float = Field(ge=0)
    rate_type: RateType = "EA"
    months: int = Field(gt=0, le=600)
    extra: float = Field(default=0, ge=0)


class PayoffSimIn(BaseModel):
    balance: float = Field(gt=0)
    rate: float = Field(ge=0)
    rate_type: RateType = "EA"
    payment: float = Field(gt=0)


class SavingsSimIn(BaseModel):
    target: float = Field(gt=0)
    current: float = Field(default=0, ge=0)
    rate: float = Field(default=0, ge=0)
    rate_type: RateType = "EA"
    months: int = Field(gt=0, le=600)
