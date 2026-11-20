from __future__ import annotations

import json

from business_os.engine import LedgerEnforcedBusinessOS


def run_demo() -> dict[str, object]:
    os_engine = LedgerEnforcedBusinessOS()

    # 1. Create deal and advance stage (probability updates deterministically)
    os_engine.create_deal("D-101", "Acme Corp", amount_cents=250_000, stage="prospecting")
    deal = os_engine.update_deal_stage("D-101", "closed_won")

    # 2. Quote -> Invoice -> Payment with foreign-key provenance
    os_engine.create_quote("D-101", "Q-101")
    link_invoiced, je_invoice = os_engine.issue_invoice("Q-101", "INV-101", "JE-101")
    link_paid, je_payment = os_engine.record_payment("INV-101", "JE-102")

    # 3. Scoped AI Copilot read and blocked mutation on posted journal entry
    copilot_read = os_engine.run_copilot_tool("read_pipeline", actor="copilot-agent")
    copilot_blocked = os_engine.run_copilot_tool(
        "post_journal_entry",
        actor="copilot-agent",
        payload={
            "entry_id": "JE-101",
            "reference_id": "INV-101",
            "description": "Unauthorized overwrite attempt",
            "lines": [],
        },
    )

    dashboard = os_engine.get_unified_dashboard()
    return {
        "deal": deal.model_dump(),
        "quote_invoice_link": link_paid.model_dump(),
        "posted_entries": [je_invoice.entry_id, je_payment.entry_id],
        "copilot_read_allowed": copilot_read["allowed"],
        "copilot_mutation_blocked": not copilot_blocked["allowed"],
        "copilot_block_reason": copilot_blocked["reason"],
        "dashboard": dashboard,
        "audit_log_count": len(os_engine.audit_logs),
    }


def main() -> None:
    summary = run_demo()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
