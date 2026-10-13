from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
class AccountIn(BaseModel):
    name: str
    type: Literal["cash", "bank", "wallet"] = "bank"
    initial_balance: Decimal = Decimal(0)
    currency: str = "COP"


class AccountOut(ORM, AccountIn):
    id: int
    balance: Decimal = Decimal(0)


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


# --- ahorro ---
class GoalIn(BaseModel):
    name: str
    target_amount: Decimal = Field(gt=0)
    current_amount: Decimal = Field(default=Decimal(0), ge=0)
    target_date: date
    annual_rate: Decimal = Field(default=Decimal(0), ge=0)


class GoalOut(ORM, GoalIn):
    id: int


class ContributionIn(BaseModel):
    amount: Decimal = Field(gt=0)


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
