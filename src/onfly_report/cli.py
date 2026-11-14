"""Interface de linha de comando do consolidador."""

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from pathlib import Path

from .exceptions import InputFileError
from .logging_config import configure_logging
from .repositories.csv_rate_repository import CsvRateRepository
from .repositories.csv_reservation_repository import CsvReservationRepository
from .services.report_builder import ReportBuilder

logger = logging.getLogger("onfly_report")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="onfly_report",
        description="Consolida a exportação de reservas de hotel em um relatório JSON.",
    )
    parser.add_argument("--input", required=True, help="CSV de reservas")
    parser.add_argument("--rates", required=True, help="CSV de taxas de câmbio para BRL")
    parser.add_argument("--output", default="output/report.json", help="caminho do relatório JSON")
    parser.add_argument("--top", type=int, default=5, help="quantidade de hotéis no ranking")
    return parser


def write_atomically(path: Path, content: str) -> None:
    """Grava em um temporário no mesmo diretório e troca de uma vez com os.replace.

    Se o processo cair no meio, ou duas execuções gravarem o mesmo --output, nunca sobra
    um JSON truncado: quem lê vê o relatório anterior ou o novo inteiro.
    """
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.top < 1:
        parser.error("--top deve ser maior ou igual a 1")

    try:
        report = ReportBuilder(
            reservation_repository=CsvReservationRepository(Path(args.input)),
            rate_repository=CsvRateRepository(Path(args.rates)),
            top_n=args.top,
        ).build()
    except InputFileError as err:
        logger.error("falha ao ler a entrada: %s", err)
        return 2
    except Exception:
        logger.exception("erro inesperado ao gerar o relatório")
        return 1

    output_path = Path(args.output)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(output_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        logger.exception("falha ao escrever o relatório em %s", output_path)
        return 1

    summary = report["summary"]
    print(
        "Reservas: {total} | Confirmadas: {confirmed} | Noites: {nights} | Total BRL: {amount}".format(
            total=summary["total_reservations"],
            confirmed=summary["confirmed_reservations"],
            nights=summary["total_room_nights"],
            amount=summary["total_amount_brl"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
