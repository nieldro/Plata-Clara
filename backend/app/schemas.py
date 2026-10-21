import datetime as _dt  # para campos llamados «date» con valor por defecto (si no, tapan el tipo)
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, StringConstraints, model_validator

RateType = Literal["EA", "MV", "NA"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth ---
def _clean_email(value):
    return value.strip().lower() if isinstance(value, str) else value


# Correo sin espacios alrededor y en minúsculas: «Ana@Correo.co » y «ana@correo.co» son la misma cuenta.
NormalizedEmail = Annotated[EmailStr, BeforeValidator(_clean_email)]


class RegisterIn(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=8)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class UserOut(ORM):
    id: int
    email: EmailStr
    name: str


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class DeleteAccountIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


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


class AccountUpdate(BaseModel):
    """Cambios parciales a una cuenta. Los campos de tarjeta solo valen para tarjetas de crédito."""
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    initial_balance: Decimal | None = None          # corrige el saldo con el que abriste la cuenta (no aplica a tarjetas)
    credit_limit: Decimal | None = Field(default=None, gt=0)
    rate: Decimal | None = Field(default=None, ge=0)
    rate_type: RateType | None = None
    monthly_payment: Decimal | None = Field(default=None, gt=0)  # null = quitar el pago habitual
    due_day: int | None = Field(default=None, ge=1, le=31)       # null = quitar el día de pago

    @model_validator(mode="after")
    def _not_null_where_required(self):
        for field in ("name", "initial_balance", "credit_limit", "rate", "rate_type"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"«{field}» no puede quedar vacío")
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
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    kind: Literal["income", "expense"]


class CategoryRename(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class CategoryOut(ORM, CategoryIn):
    id: int


class TransactionIn(BaseModel):
    account_id: int
    category_id: int | None = None
    kind: Literal["income", "expense"]
    amount: Decimal = Field(gt=0)
    date: date
    note: str = ""
    tags: list[str] = []


class TransactionOut(ORM, TransactionIn):
    id: int
    transfer_id: str | None = None
    tags: list[str] = Field(default_factory=list, validation_alias="tag_names")
    attachments: int = Field(default=0, validation_alias="attachment_count")
    loan_id: int | None = None


class TransactionUpdate(BaseModel):
    """Cambios parciales: solo se modifica lo que se envía."""
    account_id: int | None = None
    category_id: int | None = None
    clear_category: bool = False  # para dejarla «sin categoría» (category_id=None significa «no cambiar»)
    kind: Literal["income", "expense"] | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    date: _dt.date | None = None
    note: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = None  # None = no cambiar; [] = quitar todas


class TagRename(BaseModel):
    name: str = Field(min_length=1, max_length=60)  # se normaliza en la ruta (#, mayúsculas, espacios)


class BulkIn(BaseModel):
    """Una acción aplicada a varios movimientos a la vez."""
    ids: list[int] = Field(min_length=1, max_length=200)
    action: Literal["delete", "set_category", "add_tag", "remove_tag"]
    category_id: int | None = None
    clear_category: bool = False   # set_category sin categoría: deja los movimientos «sin categoría»
    tag: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def _consistent(self):
        self.ids = list(dict.fromkeys(self.ids))  # sin repetidos, conservando el orden
        if self.action == "set_category" and self.category_id is None and not self.clear_category:
            raise ValueError("Elige una categoría (o indica que quieres dejarlos sin categoría)")
        if self.action in ("add_tag", "remove_tag") and not (self.tag or "").strip().lstrip("#").strip():
            raise ValueError("Escribe el nombre de la etiqueta")
        return self


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


# --- préstamos y gastos compartidos ---
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class LoanIn(BaseModel):
    person: PersonName
    direction: Literal["lent", "borrowed"]
    amount: Decimal = Field(gt=0, lt=Decimal("1000000000000"))
    date: _dt.date
    due_date: _dt.date | None = None
    note: str = Field(default="", max_length=255)
    account_id: int | None = None  # si se indica, el dinero entra o sale de esa cuenta

    @model_validator(mode="after")
    def _due_after_date(self):
        if self.due_date and self.due_date < self.date:
            raise ValueError("La fecha límite no puede ser anterior al préstamo")
        return self


class LoanUpdate(BaseModel):
    person: PersonName | None = None
    note: str | None = Field(default=None, max_length=255)
    due_date: _dt.date | None = None
    clear_due_date: bool = False


class LoanPaymentIn(BaseModel):
    amount: Decimal = Field(gt=0, lt=Decimal("1000000000000"))
    date: _dt.date
    note: str = Field(default="", max_length=255)
    account_id: int | None = None


class SplitParticipant(BaseModel):
    person: PersonName
    amount: Decimal | None = Field(default=None, gt=0)  # None en todos = partes iguales


class SplitIn(BaseModel):
    account_id: int
    category_id: int | None = None
    total: Decimal = Field(gt=0, lt=Decimal("1000000000000"))
    date: _dt.date
    note: str = Field(default="", max_length=255)
    due_date: _dt.date | None = None
    participants: list[SplitParticipant] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _consistent(self):
        given = [p.amount is not None for p in self.participants]
        if any(given) and not all(given):
            raise ValueError("Indica el monto de todos los participantes o de ninguno (partes iguales)")
        return self


# --- importación de extractos ---
class ImportRowIn(BaseModel):
    date: _dt.date
    description: str = Field(default="", max_length=255)
    amount: Decimal = Field(gt=0, lt=Decimal("1000000000000"))
    kind: Literal["income", "expense"]
    category_id: int | None = None
    import_hash: str = Field(min_length=40, max_length=40, pattern="^[0-9a-f]{40}$")
    tags: list[str] = []


class ImportCommitIn(BaseModel):
    account_id: int
    rows: list[ImportRowIn] = Field(min_length=1, max_length=2000)


# --- reglas de categorización ---
class RuleIn(BaseModel):
    keyword: str = Field(min_length=1, max_length=60)
    category_id: int


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


class ApplyBudgetItem(BaseModel):
    category_id: int
    amount: Decimal = Field(gt=0, lt=Decimal("1000000000000"))


class ApplyBudgetsIn(BaseModel):
    items: list[ApplyBudgetItem] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _no_repeats(self):
        ids = [i.category_id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Hay categorías repetidas")
        return self


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
