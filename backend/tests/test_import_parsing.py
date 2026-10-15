from datetime import date
from decimal import Decimal

import pytest

from app.services import importer
from app.services.importer import detect_mapping, find_header, parse_amount, parse_date, read_csv


@pytest.mark.parametrize("raw,expected", [
    ("$ 1.234.567,89", "1234567.89"),
    ("1,234,567.89", "1234567.89"),
    ("50.000", "50000"),          # en pesos, 3 dígitos tras el punto son miles
    ("1,234", "1234"),
    ("12,5", "12.5"),
    ("12.50", "12.50"),
    ("-50.000", "-50000"),
    ("(50.000)", "-50000"),
    ("50.000-", "-50000"),
    ("+75000", "75000"),
    ("COP 2.500.000", "2500000"),
    ("1.234.567", "1234567"),
])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["", "   ", "abc", "-", "$"])
def test_parse_amount_rejects_garbage(raw):
    assert parse_amount(raw) is None


def test_parse_date_formats_and_order():
    assert parse_date("2026-03-05") == date(2026, 3, 5)
    assert parse_date("05/03/2026") == date(2026, 3, 5)               # día/mes por defecto
    assert parse_date("05/03/2026", "mdy") == date(2026, 5, 3)
    assert parse_date("31/12/25") == date(2025, 12, 31)
    assert parse_date("2026-03-05 14:30:00") == date(2026, 3, 5)
    assert parse_date("5-3-2026") == date(2026, 3, 5)
    assert parse_date("5/3/2026") == date(2026, 3, 5)
    assert parse_date("31/02/2026") is None
    assert parse_date("00/00/0000") is None
    assert parse_date("01/01/1850") is None  # año absurdo
    assert parse_date("") is None


def test_header_detection_skips_summary_lines_and_accents():
    rows = [
        ["Extracto de cuenta de ahorros", "", ""],
        ["Titular: Daniel", "", ""],
        ["Fecha", "Descripción", "Valor", "Saldo"],
        ["05/03/2026", "COMPRA EXITO", "-50.000", "950.000"],
    ]
    assert find_header(rows) == 2
    assert detect_mapping(rows[2]) == {"date": 0, "debit": None, "credit": None, "amount": 2, "description": 1}


def test_debit_credit_columns_detected_without_stealing_amount():
    m = detect_mapping(["Fecha de transacción", "Detalle", "Valor débito", "Valor crédito"])
    assert m["date"] == 0 and m["description"] == 1 and m["debit"] == 2 and m["credit"] == 3 and m["amount"] is None


def test_read_csv_handles_semicolon_and_windows_1252():
    data = "Fecha;Descripción;Valor\n05/03/2026;Droguería;-12.000\n".encode("cp1252")
    rows = read_csv(data)
    assert rows[0] == ["Fecha", "Descripción", "Valor"] and rows[1][1] == "Droguería"
    assert read_csv(b"a,b,c\n1,2,3")[1] == ["1", "2", "3"]
    assert read_csv("﻿fecha\tvalor\n1\t2".encode("utf-8"))[0] == ["fecha", "valor"]


def test_read_table_rejects_unknown_and_empty():
    with pytest.raises(importer.ImportError_):
        importer.read_table("extracto.pdf", b"x")
    with pytest.raises(importer.ImportError_):
        importer.read_table("vacio.csv", b"")
    with pytest.raises(importer.ImportError_):
        importer.read_table("vacio.csv", b",,\n,,\n")


def test_build_rows_signs_invert_errors_and_repeated_lines():
    rows = [
        ["Fecha", "Descripción", "Valor"],
        ["05/03/2026", "Café", "-4.000"],
        ["05/03/2026", "Café", "-4.000"],       # dos cafés iguales: ambos válidos, huellas distintas
        ["06/03/2026", "Nómina", "3.000.000"],
        ["fecha rara", "X", "100"],
        ["07/03/2026", "Sin monto", ""],
        ["", "", ""],                            # fila vacía se ignora
    ]
    mapping = detect_mapping(rows[0])
    parsed = importer.build_rows(rows, mapping, 0, account_id=1)
    assert [(p.kind, p.amount) for p in parsed[:3]] == [
        ("expense", Decimal("4000.00")), ("expense", Decimal("4000.00")), ("income", Decimal("3000000.00"))]
    assert parsed[0].import_hash != parsed[1].import_hash
    assert parsed[3].error and "Fecha" in parsed[3].error
    assert parsed[4].error and len(parsed) == 5

    inverted = importer.build_rows(rows, mapping, 0, account_id=1, invert=True)
    assert inverted[0].kind == "income" and inverted[2].kind == "expense"


def test_build_rows_with_debit_and_credit_columns():
    rows = [["Fecha", "Detalle", "Débito", "Crédito"],
            ["01/04/2026", "Retiro cajero", "200.000", ""],
            ["02/04/2026", "Abono nómina", "", "1.500.000"],
            ["03/04/2026", "Vacío", "", ""]]
    parsed = importer.build_rows(rows, detect_mapping(rows[0]), 0, account_id=1)
    assert (parsed[0].kind, parsed[0].amount) == ("expense", Decimal("200000.00"))
    assert (parsed[1].kind, parsed[1].amount) == ("income", Decimal("1500000.00"))
    assert parsed[2].error


def test_build_rows_requires_mapping():
    with pytest.raises(importer.ImportError_):
        importer.build_rows([["a"]], {"date": None, "amount": 1, "debit": None, "credit": None, "description": None}, None, account_id=1)
    with pytest.raises(importer.ImportError_):
        importer.build_rows([["a"]], {"date": 0, "amount": None, "debit": None, "credit": None, "description": None}, None, account_id=1)
