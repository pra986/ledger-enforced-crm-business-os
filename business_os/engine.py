from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from business_os.models import (
    STAGE_PROBABILITIES,
    CopilotAuditLog,
    DealRecord,
    DealStage,
    JournalEntry,
    JournalLine,
    QuoteInvoiceLink,
)

ALLOWED_COPILOT_TOOLS = frozenset({"read_pipeline", "draft_quote", "post_journal_entry"})


class LedgerEnforcedBusinessOS:
    """Unified CRM, quote-to-invoice, double-entry ledger, and audited Copilot engine."""

    def __init__(self) -> None:
        self.deals: dict[str, DealRecord] = {}
        self.quote_links: dict[str, QuoteInvoiceLink] = {}
        self.journal_entries: dict[str, JournalEntry] = {}
        self.audit_logs: list[CopilotAuditLog] = []
        self._audit_seq = 0
        self._link_seq = 0

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_deal(
        self,
        deal_id: str,
        account_name: str,
        amount_cents: int,
        stage: DealStage = "prospecting",
    ) -> DealRecord:
        if deal_id in self.deals:
            raise ValueError(f"Deal '{deal_id}' already exists.")
        deal = DealRecord(
            deal_id=deal_id,
            account_name=account_name,
            stage=stage,
            amount_cents=amount_cents,
            probability=STAGE_PROBABILITIES[stage],
        )
        self.deals[deal_id] = deal
        return deal

    def update_deal_stage(self, deal_id: str, new_stage: DealStage) -> DealRecord:
        if deal_id not in self.deals:
            raise KeyError(f"Deal '{deal_id}' not found.")
        current = self.deals[deal_id]
        updated = DealRecord(
            deal_id=current.deal_id,
            account_name=current.account_name,
            stage=new_stage,
            amount_cents=current.amount_cents,
            probability=STAGE_PROBABILITIES[new_stage],
        )
        self.deals[deal_id] = updated
        return updated

    def create_quote(
        self,
        deal_id: str,
        quote_id: str,
        amount_cents: int | None = None,
        currency: str = "USD",
    ) -> QuoteInvoiceLink:
        if deal_id not in self.deals:
            raise KeyError(f"Foreign-key violation: deal '{deal_id}' does not exist.")
        for existing in self.quote_links.values():
            if existing.quote_id == quote_id:
                raise ValueError(f"Quote '{quote_id}' already exists.")
        deal = self.deals[deal_id]
        self._link_seq += 1
        link_id = f"LNK-{self._link_seq:04d}"
        link = QuoteInvoiceLink(
            link_id=link_id,
            deal_id=deal_id,
            quote_id=quote_id,
            invoice_id=None,
            amount_cents=amount_cents if amount_cents is not None else deal.amount_cents,
            currency=currency,
            status="quoted",
        )
        self.quote_links[link_id] = link
        return link

    def issue_invoice(
        self,
        quote_id: str,
        invoice_id: str,
        entry_id: str,
    ) -> tuple[QuoteInvoiceLink, JournalEntry]:
        link = self._find_link_by_quote(quote_id)
        if link.invoice_id is not None:
            raise ValueError(f"Quote '{quote_id}' already has invoice '{link.invoice_id}'.")
        updated_link = link.model_copy(update={"invoice_id": invoice_id, "status": "invoiced"})
        self.quote_links[link.link_id] = updated_link
        entry = JournalEntry(
            entry_id=entry_id,
            reference_id=invoice_id,
            description=f"Invoice {invoice_id} for deal {link.deal_id} / quote {quote_id}",
            lines=[
                JournalLine(
                    account_code="1200",
                    account_name="Accounts Receivable",
                    debit_cents=link.amount_cents,
                    credit_cents=0,
                ),
                JournalLine(
                    account_code="4000",
                    account_name="Revenue",
                    debit_cents=0,
                    credit_cents=link.amount_cents,
                ),
            ],
        )
        posted_entry = self.post_journal_entry(entry)
        return updated_link, posted_entry

    def record_payment(self, invoice_id: str, entry_id: str) -> tuple[QuoteInvoiceLink, JournalEntry]:
        link = self._find_link_by_invoice(invoice_id)
        if link.status == "paid":
            raise ValueError(f"Invoice '{invoice_id}' is already paid.")
        updated_link = link.model_copy(update={"status": "paid"})
        self.quote_links[link.link_id] = updated_link
        entry = JournalEntry(
            entry_id=entry_id,
            reference_id=invoice_id,
            description=f"Payment received for invoice {invoice_id} (deal {link.deal_id})",
            lines=[
                JournalLine(
                    account_code="1000",
                    account_name="Cash",
                    debit_cents=link.amount_cents,
                    credit_cents=0,
                ),
                JournalLine(
                    account_code="1200",
                    account_name="Accounts Receivable",
                    debit_cents=0,
                    credit_cents=link.amount_cents,
                ),
            ],
        )
        posted_entry = self.post_journal_entry(entry)
        return updated_link, posted_entry

    def _find_link_by_quote(self, quote_id: str) -> QuoteInvoiceLink:
        for link in self.quote_links.values():
            if link.quote_id == quote_id:
                return link
        raise KeyError(f"Quote '{quote_id}' not found.")

    def _find_link_by_invoice(self, invoice_id: str) -> QuoteInvoiceLink:
        for link in self.quote_links.values():
            if link.invoice_id == invoice_id:
                return link
        raise KeyError(f"Invoice '{invoice_id}' not found.")

    def post_journal_entry(self, entry: JournalEntry) -> JournalEntry:
        if entry.entry_id in self.journal_entries and self.journal_entries[entry.entry_id].posted:
            raise ValueError(f"Journal entry '{entry.entry_id}' is already posted and immutable.")
        entry.assert_balanced()
        posted_entry = entry.model_copy(update={"posted": True})
        self.journal_entries[posted_entry.entry_id] = posted_entry
        return posted_entry

    def get_trial_balance(self) -> dict[str, Any]:
        accounts: dict[str, dict[str, Any]] = {}
        total_debits = 0
        total_credits = 0
        for entry in self.journal_entries.values():
            if not entry.posted:
                continue
            for line in entry.lines:
                acct = accounts.setdefault(
                    line.account_code,
                    {
                        "account_code": line.account_code,
                        "account_name": line.account_name,
                        "debit_cents": 0,
                        "credit_cents": 0,
                        "net_cents": 0,
                    },
                )
                acct["debit_cents"] += line.debit_cents
                acct["credit_cents"] += line.credit_cents
                acct["net_cents"] = acct["debit_cents"] - acct["credit_cents"]
                total_debits += line.debit_cents
                total_credits += line.credit_cents
        return {
            "accounts": accounts,
            "total_debits_cents": total_debits,
            "total_credits_cents": total_credits,
            "balanced": total_debits == total_credits,
        }

    def get_unified_dashboard(self) -> dict[str, Any]:
        total_pipeline_cents = sum(d.amount_cents for d in self.deals.values())
        weighted_pipeline_cents = sum(int(round(d.amount_cents * d.probability)) for d in self.deals.values())
        crm_invoiced_cents = sum(
            link.amount_cents for link in self.quote_links.values() if link.status in ("invoiced", "paid")
        )
        crm_paid_cents = sum(
            link.amount_cents for link in self.quote_links.values() if link.status == "paid"
        )
        trial_balance = self.get_trial_balance()
        revenue_acct = trial_balance["accounts"].get("4000", {})
        ledger_revenue_cents = revenue_acct.get("credit_cents", 0) - revenue_acct.get("debit_cents", 0)
        cash_acct = trial_balance["accounts"].get("1000", {})
        ledger_cash_cents = cash_acct.get("debit_cents", 0) - cash_acct.get("credit_cents", 0)
        return {
            "deal_count": len(self.deals),
            "total_pipeline_cents": total_pipeline_cents,
            "weighted_pipeline_cents": weighted_pipeline_cents,
            "crm_invoiced_cents": crm_invoiced_cents,
            "crm_paid_cents": crm_paid_cents,
            "ledger_revenue_cents": ledger_revenue_cents,
            "ledger_cash_cents": ledger_cash_cents,
            "trial_balance_debits_cents": trial_balance["total_debits_cents"],
            "trial_balance_credits_cents": trial_balance["total_credits_cents"],
            "trial_balance_balanced": trial_balance["balanced"],
            "revenue_parity": crm_invoiced_cents == ledger_revenue_cents,
            "cash_parity": crm_paid_cents == ledger_cash_cents,
        }

    def _record_audit(
        self,
        tool_name: str,
        actor: str,
        payload_summary: str,
        allowed: bool,
        reason: str,
    ) -> CopilotAuditLog:
        self._audit_seq += 1
        log = CopilotAuditLog(
            audit_id=f"AUD-{self._audit_seq:04d}",
            tool_name=tool_name,
            actor=actor,
            payload_summary=payload_summary,
            allowed=allowed,
            reason=reason,
            timestamp=self._now_iso(),
        )
        self.audit_logs.append(log)
        return log

    def run_copilot_tool(
        self,
        tool_name: str,
        actor: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = payload or {}
        summary = f"keys={sorted(payload.keys())}"

        if tool_name not in ALLOWED_COPILOT_TOOLS:
            reason = f"Tool '{tool_name}' is outside the scoped copilot allowlist."
            log = self._record_audit(tool_name, actor, summary, False, reason)
            return {"allowed": False, "reason": reason, "audit_id": log.audit_id}

        if tool_name == "read_pipeline":
            log = self._record_audit(tool_name, actor, summary, True, "Read-only pipeline access granted.")
            return {
                "allowed": True,
                "audit_id": log.audit_id,
                "result": {
                    "deals": [d.model_dump() for d in self.deals.values()],
                    "dashboard": self.get_unified_dashboard(),
                },
            }

        if tool_name == "draft_quote":
            try:
                link = self.create_quote(
                    deal_id=payload["deal_id"],
                    quote_id=payload["quote_id"],
                    amount_cents=payload.get("amount_cents"),
                    currency=payload.get("currency", "USD"),
                )
            except (KeyError, ValueError) as exc:
                log = self._record_audit(tool_name, actor, summary, False, str(exc))
                return {"allowed": False, "reason": str(exc), "audit_id": log.audit_id}
            log = self._record_audit(tool_name, actor, summary, True, f"Drafted quote {link.quote_id}.")
            return {"allowed": True, "audit_id": log.audit_id, "result": link.model_dump()}

        if tool_name == "post_journal_entry":
            entry_id = payload.get("entry_id")
            if entry_id in self.journal_entries and self.journal_entries[entry_id].posted:
                reason = f"Blocked mutation of posted immutable journal entry '{entry_id}'."
                log = self._record_audit(tool_name, actor, summary, False, reason)
                return {"allowed": False, "reason": reason, "audit_id": log.audit_id}
            try:
                lines = [JournalLine(**line) for line in payload["lines"]]
                entry = JournalEntry(
                    entry_id=payload["entry_id"],
                    reference_id=payload["reference_id"],
                    description=payload["description"],
                    lines=lines,
                )
                posted = self.post_journal_entry(entry)
            except (KeyError, ValueError, TypeError) as exc:
                log = self._record_audit(tool_name, actor, summary, False, str(exc))
                return {"allowed": False, "reason": str(exc), "audit_id": log.audit_id}
            log = self._record_audit(tool_name, actor, summary, True, f"Posted journal entry {posted.entry_id}.")
            return {"allowed": True, "audit_id": log.audit_id, "result": posted.model_dump()}

        reason = f"Unhandled tool '{tool_name}'."
        log = self._record_audit(tool_name, actor, summary, False, reason)
        return {"allowed": False, "reason": reason, "audit_id": log.audit_id}
