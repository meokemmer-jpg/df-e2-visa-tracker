"""
E2-Visa-Tracker Core-Logic [CRUX-MK]
Sandbox-Default. Anwalt-Coordination via Stub.

K_0 Touch: Investment-Threshold + Anwaltskosten
Q_0 Touch: Familien-Lebensmittelpunkt-Wechsel
"""
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


# E-2-Visa Investment-Threshold (USCIS-Guidance)
E2_INVESTMENT_THRESHOLD_USD = 100_000  # "substantial" Minimum
E2_PASSIVE_INVESTMENT_FORBIDDEN = True  # active enterprise mandatory


@dataclass(frozen=True)
class E2Document:
    """E-2-Filing Document-Item."""
    doc_id: str
    name: str
    category: str  # "business-plan" | "investment-proof" | "hire-plan" | "source-of-funds" | "treaty-country"
    status: str  # "missing" | "draft" | "review" | "final"
    last_updated: str


@dataclass
class E2VisaStatus:
    """E-2-Visa Filing-Status."""
    application_id: str
    stage: str  # "pre-file" | "filed" | "rfe" (Request-For-Evidence) | "approved" | "renewed" | "denied"
    investment_usd: int
    investment_active_pct: float  # active vs passive (USCIS Pflicht: aktiv)
    documents_complete_pct: float
    anwalt_coordinated: bool
    next_action: str
    timestamp: str


# Default-Document-Checklist (USCIS Form DS-160 + I-129 fuer Treaty-Investor)
DEFAULT_CHECKLIST = [
    E2Document("DOC-001", "Detailed Business Plan (5-Year)", "business-plan", "missing", "2026-05-11"),
    E2Document("DOC-002", "Source of Funds Documentation", "source-of-funds", "missing", "2026-05-11"),
    E2Document("DOC-003", "Investment Wire-Transfer-Proof", "investment-proof", "missing", "2026-05-11"),
    E2Document("DOC-004", "USA-LLC Operating Agreement", "investment-proof", "missing", "2026-05-11"),
    E2Document("DOC-005", "USA-Hire-Plan (5-Jahre Mitarbeiter)", "hire-plan", "missing", "2026-05-11"),
    E2Document("DOC-006", "Treaty-Country-Proof (DE-Pass)", "treaty-country", "draft", "2026-05-11"),
    E2Document("DOC-007", "Marketing Plan + Pipeline (USA)", "business-plan", "missing", "2026-05-11"),
    E2Document("DOC-008", "Office Lease / Property Documentation", "investment-proof", "missing", "2026-05-11"),
]


class E2VisaTracker:
    """E-2-Visa Tracker mit Document-Checklist + Status-Pipeline."""

    def __init__(self, real_enabled: Optional[bool] = None):
        if real_enabled is None:
            real_enabled = os.environ.get("DF_E2_VISA_REAL_ENABLED", "false").lower() == "true"
        self.real_enabled = real_enabled
        self.phronesis_ticket = os.environ.get("PHRONESIS_TICKET", "MISSING")

        if self.real_enabled and self.phronesis_ticket == "MISSING":
            raise RuntimeError(
                "K13-PAV-VIOLATION: E2-Visa-Real-Mode ohne PHRONESIS_TICKET. "
                "Anwalts-Coordination + Filing K_0 Pflicht."
            )

    def get_default_checklist(self) -> list[E2Document]:
        return list(DEFAULT_CHECKLIST)

    def compute_completion_pct(self, docs: list[E2Document]) -> float:
        """Prozent dokumente final."""
        if not docs:
            return 0.0
        finals = sum(1 for d in docs if d.status == "final")
        return round(finals / len(docs) * 100, 1)

    def validate_investment(self, amount_usd: int, active_pct: float) -> tuple[bool, list[str]]:
        """Validiert Investment gegen E-2-Anforderungen.

        Returns: (is_valid, list_of_issues)
        """
        issues = []
        if amount_usd < E2_INVESTMENT_THRESHOLD_USD:
            issues.append(
                f"Investment ${amount_usd} < ${E2_INVESTMENT_THRESHOLD_USD} substantial-threshold"
            )
        if active_pct < 80.0:
            issues.append(
                f"Active-Investment {active_pct}% < 80% (USCIS verlangt active-enterprise)"
            )
        return (len(issues) == 0, issues)

    def stage_transition_allowed(self, current: str, target: str) -> bool:
        """Validiert State-Transition (Pre-File -> Filed -> Approved)."""
        allowed = {
            "pre-file": ["filed"],
            "filed": ["rfe", "approved", "denied"],
            "rfe": ["approved", "denied"],
            "approved": ["renewed"],
            "renewed": ["renewed"],
            "denied": [],
        }
        return target in allowed.get(current, [])

    def to_status(
        self,
        application_id: str,
        stage: str,
        investment_usd: int,
        investment_active_pct: float,
        docs: list[E2Document],
        anwalt_coordinated: bool,
    ) -> E2VisaStatus:
        comp_pct = self.compute_completion_pct(docs)
        if stage == "pre-file" and comp_pct < 100.0:
            next_action = f"Complete {100 - comp_pct}% docs + Anwalt-Review"
        elif stage == "pre-file":
            next_action = "Submit DS-160 + I-129 via Anwalt"
        elif stage == "filed":
            next_action = "Await USCIS-Decision (avg 90-180d)"
        elif stage == "rfe":
            next_action = "Respond to RFE within 87 days"
        elif stage == "approved":
            next_action = "Begin USA-Operations / Schedule Visa-Renewal"
        elif stage == "renewed":
            next_action = "Continue Operations / Plan EB-5 oder I-526 Path"
        elif stage == "denied":
            next_action = "Anwalt-Coordination: Refile oder Appeal"
        else:
            next_action = "unknown"

        return E2VisaStatus(
            application_id=application_id,
            stage=stage,
            investment_usd=investment_usd,
            investment_active_pct=investment_active_pct,
            documents_complete_pct=comp_pct,
            anwalt_coordinated=anwalt_coordinated,
            next_action=next_action,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def to_report(self) -> dict:
        docs = self.get_default_checklist()
        status = self.to_status(
            application_id="MOCK-APP-001",
            stage="pre-file",
            investment_usd=150_000,
            investment_active_pct=85.0,
            docs=docs,
            anwalt_coordinated=False,
        )
        valid, issues = self.validate_investment(status.investment_usd, status.investment_active_pct)
        return {
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_mode": "real-uscis" if self.real_enabled else "sandbox-mock",
            "phronesis_ticket": self.phronesis_ticket,
            "status": asdict(status),
            "investment_valid": valid,
            "investment_issues": issues,
            "n_docs_total": len(docs),
            "n_docs_missing": sum(1 for d in docs if d.status == "missing"),
        }
