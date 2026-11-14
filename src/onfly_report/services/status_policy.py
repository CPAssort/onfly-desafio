"""Política de status das reservas."""

from __future__ import annotations

BILLABLE_STATUS = "CONFIRMED"


def is_billable(status: str) -> bool:
    """Indica se a reserva entra nos totais financeiros e de noites.

    Lista positiva: só CONFIRMED é faturável. NO_SHOW, CANCELLED e qualquer status
    desconhecido ficam de fora dos totais.
    """
    return status == BILLABLE_STATUS
