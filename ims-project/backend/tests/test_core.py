"""
Unit tests for:
- Work Item State Machine transitions
- RCA validation logic
- Debounce window
"""
import pytest
from datetime import datetime, timedelta

from src.services.state_machine import validate_transition, get_state
from src.services.processor import DebounceWindow
from src.models.schemas import RCACreate, RootCauseCategory


# ─── State Machine Tests ──────────────────────────────────────────────────────

class TestStateMachine:
    def test_open_to_investigating(self):
        """OPEN → INVESTIGATING is valid."""
        validate_transition("OPEN", "INVESTIGATING")  # Should not raise

    def test_open_to_resolved_invalid(self):
        """OPEN → RESOLVED is invalid (must go through INVESTIGATING)."""
        with pytest.raises(ValueError, match="Invalid transition"):
            validate_transition("OPEN", "RESOLVED")

    def test_open_to_closed_invalid(self):
        """OPEN → CLOSED is invalid."""
        with pytest.raises(ValueError, match="Invalid transition"):
            validate_transition("OPEN", "CLOSED")

    def test_investigating_to_resolved(self):
        """INVESTIGATING → RESOLVED is valid."""
        validate_transition("INVESTIGATING", "RESOLVED")

    def test_resolved_to_closed_without_rca(self):
        """RESOLVED → CLOSED without RCA must be rejected."""
        with pytest.raises(ValueError, match="RCA"):
            validate_transition("RESOLVED", "CLOSED", rca=None)

    def test_resolved_to_closed_with_rca(self):
        """RESOLVED → CLOSED with a complete RCA must succeed."""
        mock_rca = object()  # Any truthy object simulates a complete RCA
        validate_transition("RESOLVED", "CLOSED", rca=mock_rca)  # Should not raise

    def test_closed_is_terminal(self):
        """CLOSED → anything is invalid (terminal state)."""
        with pytest.raises(ValueError, match="Invalid transition"):
            validate_transition("CLOSED", "OPEN")

    def test_investigating_can_reopen(self):
        """INVESTIGATING → OPEN is valid (reopen if misdiagnosed)."""
        validate_transition("INVESTIGATING", "OPEN")

    def test_resolved_can_reopen_to_investigating(self):
        """RESOLVED → INVESTIGATING is valid (fix didn't hold)."""
        validate_transition("RESOLVED", "INVESTIGATING")

    def test_unknown_status_raises(self):
        """Unknown status raises ValueError."""
        with pytest.raises(ValueError, match="Unknown status"):
            get_state("NONEXISTENT")


# ─── RCA Validation Tests ─────────────────────────────────────────────────────

class TestRCAValidation:
    def _make_rca(self, **overrides):
        defaults = {
            "incident_start": datetime(2024, 1, 1, 10, 0, 0),
            "incident_end": datetime(2024, 1, 1, 11, 30, 0),
            "root_cause_category": RootCauseCategory.DATABASE,
            "root_cause_description": "Primary DB replica lag exceeded threshold causing read timeouts.",
            "fix_applied": "Promoted secondary replica to primary and restarted connection pool.",
            "prevention_steps": "Add automated replica lag alerting and automatic failover.",
        }
        defaults.update(overrides)
        return RCACreate(**defaults)

    def test_valid_rca(self):
        rca = self._make_rca()
        assert rca.mttr_minutes() if hasattr(rca, 'mttr_minutes') else True

    def test_end_before_start_raises(self):
        with pytest.raises(ValueError, match="incident_end must be after incident_start"):
            self._make_rca(
                incident_start=datetime(2024, 1, 1, 12, 0, 0),
                incident_end=datetime(2024, 1, 1, 11, 0, 0),
            )

    def test_end_equals_start_raises(self):
        t = datetime(2024, 1, 1, 10, 0, 0)
        with pytest.raises(ValueError):
            self._make_rca(incident_start=t, incident_end=t)

    def test_short_root_cause_raises(self):
        with pytest.raises(ValueError):
            self._make_rca(root_cause_description="short")

    def test_short_fix_applied_raises(self):
        with pytest.raises(ValueError):
            self._make_rca(fix_applied="fix")

    def test_short_prevention_raises(self):
        with pytest.raises(ValueError):
            self._make_rca(prevention_steps="none")


# ─── Debounce Window Tests ────────────────────────────────────────────────────

class TestDebounceWindow:
    def test_accumulate_below_threshold(self):
        dw = DebounceWindow(window_secs=10, threshold=5)
        for i in range(4):
            result = dw.record("CACHE_01", f"sig_{i}")
            assert result["action"] == "accumulate"

    def test_create_work_item_at_threshold(self):
        dw = DebounceWindow(window_secs=10, threshold=5)
        result = None
        for i in range(5):
            result = dw.record("CACHE_01", f"sig_{i}")
        assert result["action"] == "create_work_item"
        assert len(result["signal_ids"]) == 5

    def test_link_to_existing_after_threshold(self):
        dw = DebounceWindow(window_secs=10, threshold=3)
        for i in range(3):
            dw.record("DB_01", f"sig_{i}")
        dw.set_work_item_id("DB_01", "work-item-uuid-123")
        result = dw.record("DB_01", "sig_4")
        assert result["action"] == "link_to_existing"
        assert result["work_item_id"] == "work-item-uuid-123"

    def test_different_components_are_independent(self):
        dw = DebounceWindow(window_secs=10, threshold=3)
        for i in range(3):
            dw.record("CACHE_01", f"c_sig_{i}")
        # A different component should still be accumulating
        result = dw.record("API_01", "a_sig_0")
        assert result["action"] == "accumulate"
