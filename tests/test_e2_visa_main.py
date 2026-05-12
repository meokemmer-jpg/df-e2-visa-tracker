"""Tests fuer E2VisaTracker [CRUX-MK]."""
import pytest
from src.e2_visa_main import (
    E2VisaTracker, E2_INVESTMENT_THRESHOLD_USD, DEFAULT_CHECKLIST, E2Document
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("DF_E2_VISA_REAL_ENABLED", raising=False)
    monkeypatch.delenv("PHRONESIS_TICKET", raising=False)


def test_default_sandbox_mode():
    t = E2VisaTracker()
    assert t.real_enabled is False


def test_real_mode_requires_phronesis(monkeypatch):
    monkeypatch.setenv("DF_E2_VISA_REAL_ENABLED", "true")
    with pytest.raises(RuntimeError, match="K13-PAV-VIOLATION"):
        E2VisaTracker()


def test_default_checklist_8_documents():
    t = E2VisaTracker()
    docs = t.get_default_checklist()
    assert len(docs) == 8
    categories = {d.category for d in docs}
    assert "business-plan" in categories
    assert "investment-proof" in categories
    assert "source-of-funds" in categories
    assert "hire-plan" in categories
    assert "treaty-country" in categories


def test_compute_completion_pct_zero():
    """Default-Checklist hat alles missing -> 0%."""
    t = E2VisaTracker()
    docs = t.get_default_checklist()
    pct = t.compute_completion_pct(docs)
    assert pct == 0.0


def test_compute_completion_pct_full():
    """Alle final -> 100%."""
    t = E2VisaTracker()
    docs = [
        E2Document(d.doc_id, d.name, d.category, "final", d.last_updated)
        for d in DEFAULT_CHECKLIST
    ]
    assert t.compute_completion_pct(docs) == 100.0


def test_validate_investment_below_threshold():
    t = E2VisaTracker()
    valid, issues = t.validate_investment(50_000, 100.0)
    assert valid is False
    assert any("substantial-threshold" in i for i in issues)


def test_validate_investment_passive_too_high():
    """80% active mandatory."""
    t = E2VisaTracker()
    valid, issues = t.validate_investment(150_000, 50.0)
    assert valid is False
    assert any("active-enterprise" in i for i in issues)


def test_validate_investment_ok():
    t = E2VisaTracker()
    valid, issues = t.validate_investment(150_000, 90.0)
    assert valid is True
    assert issues == []


def test_stage_transition_pre_file_to_filed_ok():
    t = E2VisaTracker()
    assert t.stage_transition_allowed("pre-file", "filed") is True


def test_stage_transition_invalid():
    """Pre-File darf nicht direkt zu Approved."""
    t = E2VisaTracker()
    assert t.stage_transition_allowed("pre-file", "approved") is False


def test_stage_transition_denied_terminal():
    """Denied ist terminal."""
    t = E2VisaTracker()
    assert t.stage_transition_allowed("denied", "approved") is False


def test_to_status_pre_file_with_missing_docs():
    t = E2VisaTracker()
    docs = t.get_default_checklist()
    status = t.to_status("APP-001", "pre-file", 150_000, 90.0, docs, anwalt_coordinated=False)
    assert "Complete" in status.next_action
    assert status.documents_complete_pct == 0.0


def test_to_report_includes_phronesis_and_validation():
    t = E2VisaTracker()
    report = t.to_report()
    assert "phronesis_ticket" in report
    assert "investment_valid" in report
    assert report["source_mode"] == "sandbox-mock"
    assert report["n_docs_total"] == 8
    # DOC-006 (Treaty-Country) ist "draft" by default, daher 7 missing
    assert report["n_docs_missing"] == 7
