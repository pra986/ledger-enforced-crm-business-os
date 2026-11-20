from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

DealStage = Literal[
    "prospecting",
    "qualified",
    "proposal",
    "negotiation",
    "closed_won",
    "closed_lost",
]

STAGE_PROBABILITIES: dict[str, float] = {
    "prospecting": 0.10,
    "qualified": 0.30,
    "proposal": 0.60,
    "negotiation": 0.80,
    "closed_won": 1.00,
    "closed_lost": 0.00,
}


class DealRecord(BaseModel):
    deal_id: str
    account_name: str
    stage: DealStage = "prospecting"
    amount_cents: int = Field(gt=0)
    probability: float = 0.10

    @model_validator(mode="after")
    def sync_probability(self) -> "DealRecord":
        self.probability = STAGE_PROBABILITIES[self.stage]
        return self


class QuoteInvoiceLink(BaseModel):
    link_id: str
    deal_id: str
    quote_id: str
    invoice_id: Optional[str] = None
    amount_cents: int = Field(gt=0)
    currency: str = "USD"
    status: Literal["quoted", "invoiced", "paid"] = "quoted"


class JournalLine(BaseModel):
    account_code: str
    account_name: str
    debit_cents: int = Field(default=0, ge=0)
    credit_cents: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_single_sided(self) -> "JournalLine":
        if (self.debit_cents > 0 and self.credit_cents > 0) or (
            self.debit_cents == 0 and self.credit_cents == 0
        ):
            raise ValueError(
                "JournalLine must have strictly positive debit_cents OR credit_cents, not both or neither."
            )
        return self


class JournalEntry(BaseModel):
    entry_id: str
    reference_id: str
    description: str
    lines: list[JournalLine]
    posted: bool = False
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def total_debits(self) -> int:
        return sum(line.debit_cents for line in self.lines)

    @property
    def total_credits(self) -> int:
        return sum(line.credit_cents for line in self.lines)

    def assert_balanced(self) -> None:
        if len(self.lines) < 2:
            raise ValueError("JournalEntry must contain at least 2 lines.")
        if self.total_debits <= 0 or self.total_debits != self.total_credits:
            raise ValueError(
                f"Unbalanced JournalEntry {self.entry_id}: "
                f"debits={self.total_debits} != credits={self.total_credits}"
            )


class CopilotAuditLog(BaseModel):
    audit_id: str
    tool_name: str
    actor: str
    payload_summary: str
    allowed: bool
    reason: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
