"""
Testes unitários do chat_service — foco em _apply_date_filter.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.chat_service import _apply_date_filter


def _make_transaction(created_at: datetime) -> MagicMock:
    t = MagicMock()
    t.created_at = created_at
    return t


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestApplyDateFilter:
    def test_no_filter_returns_last_10(self):
        """Sem filtro retorna as 10 mais recentes em ordem decrescente."""
        txs = [_make_transaction(_now() - timedelta(days=i)) for i in range(15)]
        result, label = _apply_date_filter(txs, None)
        assert len(result) == 10
        assert label == ""
        # Mais recente primeiro
        assert result[0].created_at > result[-1].created_at

    def test_hoje_includes_transactions_from_today(self):
        """date_filter='hoje' retorna apenas transações criadas hoje."""
        now = _now()
        today = [_make_transaction(now - timedelta(hours=1)), _make_transaction(now - timedelta(hours=3))]
        yesterday = [_make_transaction(now - timedelta(hours=25))]
        result, label = _apply_date_filter(today + yesterday, "hoje")
        assert len(result) == 2
        assert label == "hoje"

    def test_hoje_excludes_yesterday(self):
        """date_filter='hoje' exclui transações de ontem."""
        now = _now()
        yesterday = _make_transaction(now - timedelta(hours=25))
        result, label = _apply_date_filter([yesterday], "hoje")
        assert result == []
        assert label == "hoje"

    def test_semana_includes_last_7_days(self):
        """date_filter='semana' retorna transações dos últimos 7 dias."""
        now = _now()
        within = [_make_transaction(now - timedelta(days=i)) for i in range(7)]
        outside = [_make_transaction(now - timedelta(days=8))]
        result, label = _apply_date_filter(within + outside, "semana")
        assert len(result) == 7
        assert label == "nos últimos 7 dias"

    def test_mes_includes_current_month(self):
        """date_filter='mes' retorna transações do mês atual."""
        now = _now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month = _make_transaction(start_of_month + timedelta(hours=1))
        last_month = _make_transaction(start_of_month - timedelta(days=1))
        result, label = _apply_date_filter([this_month, last_month], "mes")
        assert len(result) == 1
        assert "mes" in label or now.strftime("%B") in label or "/" in label

    def test_result_sorted_most_recent_first(self):
        """Transações filtradas são retornadas da mais recente para a mais antiga."""
        now = _now()
        txs = [
            _make_transaction(now - timedelta(hours=3)),
            _make_transaction(now - timedelta(hours=1)),
            _make_transaction(now - timedelta(hours=2)),
        ]
        result, _ = _apply_date_filter(txs, "hoje")
        assert result[0].created_at > result[1].created_at > result[2].created_at

    def test_empty_list_returns_empty(self):
        """Lista vazia de transações retorna vazia para qualquer filtro."""
        for f in [None, "hoje", "semana", "mes"]:
            result, _ = _apply_date_filter([], f)
            assert result == []
