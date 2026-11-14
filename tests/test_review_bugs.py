"""Testes de revisão: cada teste prova um defeito ou caso de borda antes da correção.

Testes unitários chamam os módulos diretamente (sem subprocess), para isolar a causa.
Rode com: PYTHONPATH=src pytest -q tests/test_review_bugs.py
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from onfly_report.exceptions import InputFileError
from onfly_report.models import RawRow
from onfly_report.repositories.csv_rate_repository import CsvRateRepository
from onfly_report.repositories.csv_reservation_repository import CsvReservationRepository
from onfly_report.services.currency_converter import convert_to_brl
from onfly_report.services.report_builder import ReportBuilder
from onfly_report.services.status_policy import is_billable
from onfly_report.services.stay_calculator import calculate_room_nights

HEADER = (
    "reservation_id,traveler_name,company_id,hotel_id,hotel_name,city,country,checkin_date,"
    "checkout_date,rooms,status,currency,amount,payment_method,booked_at"
)
RATES = {"BRL": Decimal("1.000000"), "USD": Decimal("5.420000"), "EUR": Decimal("5.880000")}
FIXED_NOW = datetime(2025, 7, 1, 10, 0, tzinfo=timezone(timedelta(hours=-3)))


def row(n: int, **overrides: str) -> dict[str, str]:
    base = {
        "reservation_id": f"R-{n}",
        "traveler_name": "Pessoa",
        "company_id": "EMP-001",
        "hotel_id": "H01",
        "hotel_name": "Hotel A",
        "city": "SP",
        "country": "BR",
        "checkin_date": "2025-01-10",
        "checkout_date": "2025-01-11",
        "rooms": "1",
        "status": "CONFIRMED",
        "currency": "BRL",
        "amount": "100.00",
        "payment_method": "PIX",
        "booked_at": "2025-01-01T10:00:00-03:00",
    }
    base.update(overrides)
    return base


class StubReservations:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._rows = rows

    def read(self) -> list[RawRow]:
        return [RawRow(line_number=i + 2, values=dict(r)) for i, r in enumerate(self._rows)]


class StubRates:
    def __init__(self, rates: dict[str, Decimal] | None = None) -> None:
        self._rates = rates or RATES

    def read(self) -> dict[str, Decimal]:
        return dict(self._rates)


def build(rows: list[dict[str, str]], top: int = 5, rates: dict[str, Decimal] | None = None) -> dict:
    return ReportBuilder(StubReservations(rows), StubRates(rates), top_n=top, now=FIXED_NOW).build()


def write_csv(path: Path, lines: list[str], encoding: str = "utf-8") -> Path:
    path.write_text("\n".join(lines) + "\n", encoding=encoding)
    return path


# --------------------------------------------------------------------------- CRÍTICO


def test_c1_repository_reads_all_rows_not_only_200(tmp_path):
    """C1: o repositório para silenciosamente na linha 200."""
    lines = [HEADER] + [",".join(row(i).values()) for i in range(250)]
    rows = CsvReservationRepository(write_csv(tmp_path / "r.csv", lines)).read()
    assert len(rows) == 250


def test_c2_conversion_multiplies_by_rate():
    """C2a: o conversor divide pela taxa em vez de multiplicar."""
    assert convert_to_brl(Decimal("100.00"), "USD", RATES) == Decimal("542.00")


def test_c2_conversion_is_exact_decimal_without_float():
    """C2b: passar por float introduz erro binário (0.1 * 3 != 0.3 em float)."""
    assert convert_to_brl(Decimal("0.1"), "X", {"X": Decimal("3")}) == Decimal("0.3")


def test_c3_no_show_is_not_billable():
    """C3: NO_SHOW é tratado como faturável (regra só exclui CANCELLED)."""
    assert is_billable("CONFIRMED") is True
    assert is_billable("NO_SHOW") is False
    assert is_billable("CANCELLED") is False


def test_c3_unknown_status_is_not_billable():
    """C3b: a regra é por lista negativa; qualquer status novo vira faturável."""
    assert is_billable("PENDING") is False


@pytest.mark.parametrize(
    ("checkin", "checkout", "rooms", "expected"),
    [
        (date(2025, 1, 10), date(2025, 1, 13), 1, 3),
        (date(2025, 1, 30), date(2025, 2, 2), 2, 6),  # virada de mês
        (date(2024, 12, 30), date(2025, 1, 2), 1, 3),  # virada de ano
        (date(2025, 1, 15), date(2025, 2, 15), 1, 31),  # mesmo dia do mês, mês seguinte
    ],
)
def test_c4_room_nights_use_date_difference(checkin, checkout, rooms, expected):
    """C4: subtrair .day ignora mês/ano (30/01→02/02 dá -28)."""
    assert calculate_room_nights(checkin, checkout, rooms) == expected


def test_c5_top_hotels_descending_by_amount():
    """C5a: o ranking está em ordem crescente."""
    report = build(
        [
            row(1, hotel_id="H01", amount="1000.00"),
            row(2, hotel_id="H02", amount="900.00"),
            row(3, hotel_id="H03", amount="800.00"),
        ],
        top=2,
    )
    assert [h["hotel_id"] for h in report["top_hotels"]] == ["H01", "H02"]


def test_g2_top_hotels_tie_break_by_hotel_id_ascending():
    """G2 (guarda): empate no total desempata por hotel_id ascendente.

    Passa hoje por acaso (ordem toda crescente); quebra com um simples reverse=True.
    """
    report = build(
        [
            row(1, hotel_id="H09", amount="500.00"),
            row(2, hotel_id="H02", amount="500.00"),
            row(3, hotel_id="H05", amount="500.00"),
        ]
    )
    assert [h["hotel_id"] for h in report["top_hotels"]] == ["H02", "H05", "H09"]


def test_c_sample_matches_readme_table():
    """Regressão: a amostra do README (exemplo-validacao.csv) com os valores documentados."""
    import csv

    path = Path(__file__).resolve().parent.parent / "data" / "exemplo-validacao.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    report = build(rows)
    assert report["summary"] == {
        "total_reservations": 12,
        "confirmed_reservations": 9,
        "cancelled_reservations": 2,
        "no_show_reservations": 1,
        "total_room_nights": 28,
        "total_amount_brl": "7566.00",
        "average_nightly_rate_brl": "270.21",
    }
    assert report["by_month"] == [
        {"month": "2025-01", "reservations": 8, "room_nights": 25, "total_brl": "6684.00"},
        {"month": "2025-02", "reservations": 1, "room_nights": 3, "total_brl": "882.00"},
    ]
    assert [(h["hotel_id"], h["total_brl"]) for h in report["top_hotels"]] == [
        ("H01", "1200.00"),
        ("H02", "1084.00"),
        ("H12", "1000.00"),
        ("H10", "900.00"),
        ("H09", "882.00"),
    ]


# --------------------------------------------------------------------------- MÉDIO


def test_g1_rounding_only_at_serialization():
    """G1 (guarda): arredondar por linha e somar diverge de somar exato e arredondar no fim.

    3 x 0.005 USD-equivalente: exato = 0.015 -> "0.02"; arredondando cada um antes -> 0.03.
    Garante que o total é calculado sobre valores exatos.
    """
    rates = {"BRL": Decimal("1"), "X": Decimal("0.001")}
    report = build([row(i, currency="X", amount="5") for i in range(3)], rates=rates)
    assert report["summary"]["total_amount_brl"] == "0.02"


def test_m2_missing_rate_is_input_error_not_crash():
    """M2: moeda sem taxa gera KeyError (exit 1, 'erro inesperado') em vez de InputFileError (exit 2)."""
    with pytest.raises(InputFileError):
        build([row(1, currency="GBP")])


def test_b5_currency_case_is_normalized_like_rate_table():
    """B5: a tabela de câmbio faz .upper(), a reserva não; 'usd' quebra."""
    report = build([row(1, currency="usd", amount="100.00")])
    assert report["summary"]["total_amount_brl"] == "542.00"


def test_b6_status_is_normalized():
    """B6: ' confirmed' / 'Confirmed' não é contado como CONFIRMED."""
    report = build([row(1, status="confirmed")])
    assert report["summary"]["confirmed_reservations"] == 1


def test_m3_non_utf8_input_is_input_error(tmp_path):
    """M3: UnicodeDecodeError não é OSError/csv.Error -> escapa como erro inesperado (exit 1)."""
    path = tmp_path / "r.csv"
    path.write_bytes((HEADER + "\n").encode() + ",".join(row(1, traveler_name="Olívia").values()).encode("latin-1"))
    with pytest.raises(InputFileError):
        CsvReservationRepository(path).read()


def test_m4_nan_rate_is_input_error(tmp_path):
    """M4: Decimal('NaN') <= 0 lança InvalidOperation fora do try -> exit 1."""
    path = write_csv(tmp_path / "rates.csv", ["currency,rate_to_brl", "USD,NaN"])
    with pytest.raises(InputFileError):
        CsvRateRepository(path).read()


def test_m4_infinite_rate_is_rejected(tmp_path):
    """M4b: 'Infinity' passa na validação (> 0) e contamina os totais."""
    path = write_csv(tmp_path / "rates.csv", ["currency,rate_to_brl", "USD,Infinity"])
    with pytest.raises(InputFileError):
        CsvRateRepository(path).read()


def test_m5_nan_amount_is_input_error():
    """M5: amount 'NaN' é aceito pelo Decimal e explode no quantize (exit 1)."""
    with pytest.raises(InputFileError):
        build([row(1, amount="NaN")])


# --------------------------------------------------------------------------- BAIXO


def test_b1_checkout_before_checkin_is_rejected():
    """B1: checkout <= checkin gera noites zero/negativas sem aviso."""
    with pytest.raises(InputFileError):
        build([row(1, checkin_date="2025-01-13", checkout_date="2025-01-10")])


def test_b2_non_positive_rooms_is_rejected():
    """B2: rooms=0 ou negativo é aceito."""
    with pytest.raises(InputFileError):
        build([row(1, rooms="0")])


def test_b3_utf8_bom_header_is_accepted(tmp_path):
    """B3: CSV exportado pelo Excel com BOM perde a 1ª coluna (exit 2 indevido)."""
    path = tmp_path / "r.csv"
    write_csv(path, [HEADER, ",".join(row(1).values())], encoding="utf-8-sig")
    assert len(CsvReservationRepository(path).read()) == 1


def test_b4_duplicate_currency_in_rate_table_is_rejected(tmp_path):
    """B4: taxa duplicada é sobrescrita silenciosamente (última vence)."""
    path = write_csv(tmp_path / "rates.csv", ["currency,rate_to_brl", "USD,5.42", "USD,1.00"])
    with pytest.raises(InputFileError):
        CsvRateRepository(path).read()


def test_g3_zero_nights_average_is_zero():
    """G3 (guarda, deve passar): sem CONFIRMED, average é '0.00' e não divide por zero."""
    report = build([row(1, status="CANCELLED")])
    assert report["summary"]["average_nightly_rate_brl"] == "0.00"
    assert report["by_month"] == [] and report["top_hotels"] == []
