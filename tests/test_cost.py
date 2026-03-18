"""Tests for cost tracking."""

import pytest
from reasonflow.cost import calculate_cost, parse_budget, CostTracker


class TestParseBudget:
    def test_dollar_string(self):
        assert parse_budget("$0.50") == 0.50

    def test_plain_number_string(self):
        assert parse_budget("1.25") == 1.25

    def test_float(self):
        assert parse_budget(0.75) == 0.75

    def test_none(self):
        assert parse_budget(None) is None

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_budget("invalid")


class TestCalculateCost:
    def test_claude_sonnet(self):
        # $3/M input, $15/M output
        cost = calculate_cost("claude-sonnet", 1000, 500)
        expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
        assert cost == round(expected, 6)

    def test_default_model(self):
        cost = calculate_cost("unknown-model", 1000, 1000)
        expected = (1000 * 3.0 + 1000 * 15.0) / 1_000_000
        assert cost == round(expected, 6)


class TestCostTracker:
    def test_record(self):
        tracker = CostTracker()
        tracker.record("node1", "claude-sonnet", 1000, 500)
        assert tracker.total_tokens_in == 1000
        assert tracker.total_tokens_out == 500
        assert tracker.total_cost > 0

    def test_budget_not_exceeded(self):
        tracker = CostTracker(budget=1.0)
        tracker.record("node1", "claude-sonnet", 100, 50)
        assert not tracker.budget_exceeded

    def test_budget_exceeded(self):
        tracker = CostTracker(budget=0.000001)
        tracker.record("node1", "claude-sonnet", 10000, 5000)
        assert tracker.budget_exceeded

    def test_budget_remaining(self):
        tracker = CostTracker(budget=1.0)
        tracker.record("node1", "claude-sonnet", 100, 50)
        assert tracker.budget_remaining is not None
        assert tracker.budget_remaining > 0

    def test_no_budget(self):
        tracker = CostTracker()
        assert not tracker.budget_exceeded
        assert tracker.budget_remaining is None
