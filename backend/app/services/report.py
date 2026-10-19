"""Informe mensual en PDF (reportlab), pensado para imprimir: fondo blanco y acentos dorados."""
import io
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Account, Category, Debt, Loan, Transaction, User
from .loans import paid_amounts
from .notifications import cop
from .queries import (account_balances, budget_rows, month_bounds, month_totals, prev_month, spent_by_category)

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
GOLD = colors.HexColor("#B8944F")
INK = colors.HexColor("#1B1A17")
MUTED = colors.HexColor("#6F6B60")
LINE = colors.HexColor("#E3DED1")
GREEN = colors.HexColor("#2F7D52")
RED = colors.HexColor("#B04A4A")
PIE = ["#B8944F", "#7A6A45", "#D9C08A", "#4D493F", "#A9A18C", "#8F7A52", "#E8D3A2", "#6F6A5C"]
TOP_EXPENSES = 10
MAX_CATEGORIES = 12
ACCOUNT_TYPE_ES = {"savings": "Cuenta de ahorros", "checking": "Cuenta corriente", "wallet": "Billetera digital",
                   "investment": "Inversión", "cash": "Efectivo", "credit_card": "Tarjeta de crédito"}


def month_label(month: str) -> str:
    return f"{MONTHS[int(month[5:]) - 1].capitalize()} de {month[:4]}"


def _p(text: str, style) -> Paragraph:
    return Paragraph(escape(str(text)), style)  # texto del usuario escapado: una nota con «<» no rompe ni inyecta marcado


def _rich(markup: str, style) -> Paragraph:
    """Para texto con nuestras propias etiquetas (<b>). Todo dato del usuario debe ir ya escapado con escape()."""
    return Paragraph(markup, style)


def _styles():
    base = getSampleStyleSheet()["Normal"]
    base.fontName, base.fontSize, base.leading, base.textColor = "Helvetica", 9, 12, INK
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, textColor=MUTED),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=22, leading=26),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=12, leading=16,
                             textColor=GOLD, spaceBefore=14, spaceAfter=6),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.5, leading=11),
        "kpi": ParagraphStyle("kpi", parent=base, fontName="Helvetica-Bold", fontSize=14, leading=18),
    }


def _table(data, widths, header=True, align_right=()):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                  ("LINEBELOW", (0, 0), (-1, 0), 0.8, GOLD)]
    for col in align_right:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def _pie(items: list[tuple[str, float]]) -> Drawing:
    d = Drawing(170, 130)
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 15, 10, 110, 110
    pie.data = [v for _, v in items]
    pie.labels = None
    pie.slices.strokeWidth = 0.5
    pie.slices.strokeColor = colors.white
    for i in range(len(items)):
        pie.slices[i].fillColor = colors.HexColor(PIE[i % len(PIE)])
    d.add(pie)
    return d


def _pct_change(now: Decimal, before: Decimal) -> str | None:
    if before <= 0:
        return None
    change = (now - before) / before * 100
    return f"{'+' if change >= 0 else ''}{change:.0f}%"


def build_report(db: Session, user: User, month: str) -> bytes:
    s = _styles()
    start, end = month_bounds(month)
    income, expense = month_totals(db, user.id, month)
    prev = prev_month(month)
    p_income, p_expense = month_totals(db, user.id, prev)
    net = income - expense
    story = []

    story += [_p("Plata Clara", s["small"]), _p(f"Informe de {month_label(month)}", s["title"]),
              _p(f"{user.name} · generado el {clock.today().strftime('%d/%m/%Y')}", s["small"]), Spacer(1, 10)]

    # ---- resumen
    saving = f"{net / income * 100:.0f}%" if income > 0 else "—"
    kpis = Table([[_p("Ingresos", s["small"]), _p("Gastos", s["small"]), _p("Balance", s["small"]), _p("Ahorro", s["small"])],
                  [_p(cop(income), s["kpi"]), _p(cop(expense), s["kpi"]),
                   _p(("-" if net < 0 else "") + cop(abs(net)), s["kpi"]), _p(saving, s["kpi"])]],
                 colWidths=[4.4 * cm] * 4)
    kpis.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LINEAFTER", (0, 0), (-2, -1), 0.4, LINE),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(kpis)
    notes = []
    if (c := _pct_change(expense, p_expense)):
        notes.append(f"Gastos {c} frente a {MONTHS[int(prev[5:]) - 1]}")
    if (c := _pct_change(income, p_income)):
        notes.append(f"ingresos {c}")
    if notes:
        story += [Spacer(1, 4), _p(" · ".join(notes) + ".", s["small"])]

    # ---- gasto por categoría
    spent = spent_by_category(db, user.id, start, end)
    names = dict(db.execute(select(Category.id, Category.name).where(Category.user_id == user.id)).all())
    budgets = {b["category_id"]: b for b in budget_rows(db, user.id, month)}
    story.append(_p("Gasto por categoría", s["h2"]))
    if not spent:
        story.append(_p("No hay gastos registrados este mes.", s["base"]))
    else:
        ordered = sorted(spent.items(), key=lambda kv: -kv[1])
        total = sum((v for _, v in ordered), Decimal(0))
        shown = ordered[:MAX_CATEGORIES]
        rest = ordered[MAX_CATEGORIES:]
        if rest:  # la tabla va junto a la torta y no puede partirse entre páginas: se acota y el resto se agrupa
            shown = ordered[:MAX_CATEGORIES - 1]
            rest = ordered[MAX_CATEGORIES - 1:]
        rows = [["", "Categoría", "Gastado", "% del gasto", "Presupuesto", "Uso"]]
        for cat_id, amount in shown:
            b = budgets.get(cat_id)
            rows.append(["", _p(names.get(cat_id, "Sin categoría"), s["cell"]), cop(amount), f"{amount / total * 100:.0f}%",
                         cop(b["amount"]) if b else "—", f"{b['pct']:.0f}%" if b else "—"])
        if rest:
            other = sum((v for _, v in rest), Decimal(0))
            rows.append(["", _p(f"Otras ({len(rest)} categorías)", s["cell"]), cop(other),
                         f"{other / total * 100:.0f}%", "—", "—"])
        table = _table(rows, [0.35 * cm, 3.7 * cm, 2.6 * cm, 2.1 * cm, 2.6 * cm, 1.4 * cm], align_right=(2, 3, 4, 5))
        for i, (cat_id, _) in enumerate(shown, start=1):
            b = budgets.get(cat_id)
            if i <= len(PIE):  # el cuadro de color hace de leyenda de la torta
                table.setStyle(TableStyle([("BACKGROUND", (0, i), (0, i), colors.HexColor(PIE[i - 1]))]))
            if b and b["pct"] > 100:  # presupuesto excedido en rojo
                table.setStyle(TableStyle([("TEXTCOLOR", (5, i), (5, i), RED)]))
        top = [(names.get(c, "Sin categoría"), float(v)) for c, v in shown[:len(PIE)]]
        story.append(Table([[table, _pie(top)]], colWidths=[12.9 * cm, 4.1 * cm],
                           style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    # ---- mayores gastos
    biggest = db.scalars(
        select(Transaction).where(Transaction.user_id == user.id, Transaction.kind == "expense",
                                  Transaction.transfer_id.is_(None), Transaction.loan_id.is_(None),
                                  Transaction.date >= start, Transaction.date < end)
        .order_by(Transaction.amount.desc(), Transaction.id).limit(TOP_EXPENSES)).all()
    if biggest:
        story.append(_p("Mayores gastos del mes", s["h2"]))
        rows = [["Fecha", "Nota", "Categoría", "Monto"]]
        for t in biggest:
            rows.append([t.date.strftime("%d/%m"), _p(t.note or "—", s["cell"]),
                         _p(names.get(t.category_id, "Sin categoría"), s["cell"]), cop(t.amount)])
        story.append(_table(rows, [1.8 * cm, 8 * cm, 4.6 * cm, 3 * cm], align_right=(3,)))

    # ---- cuentas y patrimonio
    moved = account_balances(db, user.id)
    debts = db.scalars(select(Debt).where(Debt.user_id == user.id)).all()
    debt_by_id = {d.id: d for d in debts}
    accounts = db.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.id)).all()
    rows, cash = [["Cuenta", "Tipo", "Saldo"]], Decimal(0)
    for a in accounts:
        if a.type == "credit_card":
            owed = debt_by_id[a.debt_id].current_balance if a.debt_id in debt_by_id else Decimal(0)
            rows.append([_p(a.name, s["cell"]), "Tarjeta de crédito", "-" + cop(owed)])
        else:
            bal = a.initial_balance + (moved.get(a.id) or 0)
            cash += bal
            rows.append([_p(a.name, s["cell"]), ACCOUNT_TYPE_ES.get(a.type, a.type), cop(bal)])
    owed_total = sum((d.current_balance for d in debts), Decimal(0))
    net_worth = ("-" if cash - owed_total < 0 else "") + cop(abs(cash - owed_total))
    section = [_p("Cuentas y patrimonio", s["h2"])]
    if accounts:
        section.append(_table(rows, [8 * cm, 5.4 * cm, 4 * cm], align_right=(2,)))
    section += [Spacer(1, 6), _rich(f"Dinero en cuentas: <b>{escape(cop(cash))}</b> · Deudas: <b>{escape(cop(owed_total))}</b> · "
                                    f"Patrimonio neto: <b>{escape(net_worth)}</b>", s["base"])]
    story.append(KeepTogether(section))  # que el resumen no quede separado de su tabla por un salto de página

    # ---- préstamos pendientes
    loans = db.scalars(select(Loan).where(Loan.user_id == user.id)).all()
    if loans:
        paid = paid_amounts(db, [l.id for l in loans])
        lent = sum((l.amount - (paid.get(l.id) or 0) for l in loans if l.direction == "lent"), Decimal(0))
        borrowed = sum((l.amount - (paid.get(l.id) or 0) for l in loans if l.direction == "borrowed"), Decimal(0))
        if lent > 0 or borrowed > 0:
            story += [_p("Préstamos pendientes", s["h2"]),
                      _rich(f"Te deben <b>{escape(cop(lent))}</b> · Debes <b>{escape(cop(borrowed))}</b>", s["base"])]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(2 * cm, 1.2 * cm, f"Plata Clara · {month_label(month)}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(1.2)
        canvas.line(2 * cm, A4[1] - 1.2 * cm, A4[0] - 2 * cm, A4[1] - 1.2 * cm)
        canvas.restoreState()

    out = io.BytesIO()
    SimpleDocTemplate(out, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2 * cm,
                      title=f"Informe {month_label(month)} - Plata Clara", author="Plata Clara").build(
        story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
