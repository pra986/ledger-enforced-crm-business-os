import pytest

from business_os import (
    STAGE_PROBABILITIES,
    JournalEntry,
    JournalLine,
    LedgerEnforcedBusinessOS,
)


def test_deal_stage_probability_sync() -> None:
    os_engine = LedgerEnforcedBusinessOS()
    deal = os_engine.create_deal("D-1", "Globex", amount_cents=100_000, stage="prospecting")
    assert deal.probability == STAGE_PROBABILITIES["prospecting"]

    updated = os_engine.update_deal_stage("D-1", "negotiation")
    assert updated.stage == "negotiation"
    assert updated.probability == STAGE_PROBABILITIES["negotiation"]


def test_unbalanced_journal_entry_rejected() -> None:
    os_engine = LedgerEnforcedBusinessOS()
    unbalanced = JournalEntry(
        entry_id="JE-BAD",
        reference_id="INV-999",
        description="Unbalanced entry",
        lines=[
            JournalLine(account_code="1200", account_name="Accounts Receivable", debit_cents=50_000, credit_cents=0),
            JournalLine(account_code="4000", account_name="Revenue", debit_cents=0, credit_cents=40_000),
        ],
    )
    with pytest.raises(ValueError, match="unbalanced"):
        os_engine.post_journal_entry(unbalanced)
    assert "JE-BAD" not in os_engine.journal_entries


def test_posted_journal_immutability_against_copilot_mutations() -> None:
    os_engine = LedgerEnforcedBusinessOS()
    os_engine.create_deal("D-2", "Initech", amount_cents=75_000, stage="closed_won")
    os_engine.create_quote("D-2", "Q-2")
    _, posted_entry = os_engine.issue_invoice("Q-2", "INV-2", "JE-201")
    assert posted_entry.posted is True

    # Copilot attempts to overwrite posted entry JE-201
    res = os_engine.run_copilot_tool(
        "post_journal_entry",
        actor="copilot",
        payload={
            "entry_id": "JE-201",
            "reference_id": "INV-2",
            "description": "Tampered entry",
            "lines": [
                {"account_code": "1200", "account_name": "Accounts Receivable", "debit_cents": 1, "credit_cents": 0},
                {"account_code": "4000", "account_name": "Revenue", "debit_cents": 0, "credit_cents": 1},
            ],
        },
    )
    assert res["allowed"] is False
    assert "immutable" in res["reason"].lower()
    assert os_engine.journal_entries["JE-201"].total_debits == 75_000
    assert len(os_engine.audit_logs) == 1
    assert os_engine.audit_logs[0].allowed is False

    # Out-of-scope copilot tool is also denied and audited
    denied = os_engine.run_copilot_tool("delete_ledger", actor="copilot", payload={"entry_id": "JE-201"})
    assert denied["allowed"] is False
    assert len(os_engine.audit_logs) == 2


def test_quote_to_invoice_deal_traceability() -> None:
    os_engine = LedgerEnforcedBusinessOS()
    with pytest.raises(KeyError, match="Foreign-key violation"):
        os_engine.create_quote("MISSING-DEAL", "Q-404")

    os_engine.create_deal("D-3", "Soylent", amount_cents=120_000, stage="proposal")
    quote_link = os_engine.create_quote("D-3", "Q-3")
    assert quote_link.deal_id == "D-3"
    assert quote_link.status == "quoted"

    invoiced_link, je_inv = os_engine.issue_invoice("Q-3", "INV-3", "JE-301")
    assert invoiced_link.deal_id == "D-3"
    assert invoiced_link.quote_id == "Q-3"
    assert invoiced_link.invoice_id == "INV-3"
    assert invoiced_link.status == "invoiced"
    assert je_inv.reference_id == "INV-3"


def test_crm_dashboard_trial_balance_parity() -> None:
    os_engine = LedgerEnforcedBusinessOS()
    os_engine.create_deal("D-10", "Acme", amount_cents=200_000, stage="closed_won")
    os_engine.create_quote("D-10", "Q-10")
    os_engine.issue_invoice("Q-10", "INV-10", "JE-10")

    os_engine.create_deal("D-11", "Beta", amount_cents=100_000, stage="closed_won")
    os_engine.create_quote("D-11", "Q-11")
    os_engine.issue_invoice("Q-11", "INV-11", "JE-11")
    os_engine.record_payment("INV-11", "JE-12")

    dashboard = os_engine.get_unified_dashboard()
    assert dashboard["crm_invoiced_cents"] == 300_000
    assert dashboard["ledger_revenue_cents"] == 300_000
    assert dashboard["crm_paid_cents"] == 100_000
    assert dashboard["ledger_cash_cents"] == 100_000
    assert dashboard["revenue_parity"] is True
    assert dashboard["cash_parity"] is True
    assert dashboard["trial_balance_balanced"] is True
    assert dashboard["trial_balance_debits_cents"] == dashboard["trial_balance_credits_cents"] == 400_000
