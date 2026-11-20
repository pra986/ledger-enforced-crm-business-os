# Ledger-Enforced CRM & Business OS

**Project 31 / S1: AI SDLC — Accountable CRM and Business OS**

Full-stack CRM and double-entry accounting Business OS enforcing balanced journal invariants (`total_debits == total_credits`) across scoped AI Copilot tools, quote-to-invoice foreign-key provenance, and unified dashboard-to-trial-balance reconciliation.

> **Pinned Attribution:** Inspired by and adapted with attribution to `ed-donner/accountable`.

---

## Architecture Overview

```
+-------------------------------------------------------------------+
|                        AI Copilot Layer                           |
|   Scoped Tools: read_pipeline | draft_quote | post_journal_entry  |
|   Every invocation recorded in CopilotAuditLog (immutable)        |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                  LedgerEnforcedBusinessOS Engine                  |
|  - Stage-gated CRM deal probability updates                       |
|  - Quote -> Invoice foreign-key provenance (QuoteInvoiceLink)     |
|  - Double-entry invariant guard: sum(debits) == sum(credits)      |
|  - Posted JournalEntry immutability (rejects post-commit edits)   |
|  - Unified CRM Revenue Dashboard == Accounting Trial Balance      |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                     Persistence & API Layer                       |
|   FastAPI REST + React UI | SQLite (local) / Supabase (prod)      |
+-------------------------------------------------------------------+
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for component boundaries, invariants, and sequence diagrams.

---

## 6-Stage AI SDLC Workflow

1. **Stage 1 — Deal Capture & Stage Qualification (`DealRecord`)**: Deals enter the CRM pipeline with deterministic stage-to-probability mapping (`prospecting` 0.10, `qualified` 0.30, `proposal` 0.60, `negotiation` 0.80, `closed_won` 1.00, `closed_lost` 0.00).
2. **Stage 2 — Scoped Quote Generation (`QuoteInvoiceLink`)**: Generating a quote links `quote_id` to `deal_id` with an immutable quoted amount and currency.
3. **Stage 3 — Invoice Conversion & Provenance**: Converting a quote to an invoice enforces foreign-key traceability (`deal_id -> quote_id -> invoice_id`) and prevents orphan invoices.
4. **Stage 4 — Balanced Double-Entry Posting (`JournalEntry` / `JournalLine`)**: Posting an invoice or adjustment requires `sum(debit) == sum(credit)` in integer minor units (cents) with at least two lines; unbalanced entries are rejected before persistence.
5. **Stage 5 — Immutable Ledger Lock**: Once `posted=True`, a `JournalEntry` cannot be mutated or deleted by any user or AI Copilot tool. Corrections require a reversing journal entry.
6. **Stage 6 — Unified Reconciliation**: CRM Closed-Won Revenue Dashboard totals are computed directly against posted Revenue account credits in the Accounting Trial Balance, guaranteeing zero drift.

---

## Data Contract

| Model | Key Fields | Enforced Invariant |
|---|---|---|
| `DealRecord` | `deal_id`, `account_name`, `stage`, `amount_cents`, `probability` | Probability auto-synced to canonical stage table |
| `QuoteInvoiceLink` | `link_id`, `deal_id`, `quote_id`, `invoice_id`, `amount_cents` | Valid `deal_id` and `quote_id` required before `invoice_id` issuance |
| `JournalLine` | `account_code`, `account_name`, `debit_cents`, `credit_cents` | Non-negative amounts; each line is strictly debit XOR credit |
| `JournalEntry` | `entry_id`, `reference_id`, `lines`, `posted`, `created_at` | `sum(debit_cents) == sum(credit_cents) > 0`; immutable once `posted=True` |
| `CopilotAuditLog` | `audit_id`, `tool_name`, `actor`, `payload_summary`, `allowed`, `reason`, `timestamp` | Append-only audit trail for every AI Copilot action |

---

## Production Controls

- **Zero-Drift Accounting Invariant**: Every `JournalEntry` is validated in integer cents to eliminate floating-point rounding drift.
- **Scoped AI Copilot Permissions**: Copilot tools operate through `LedgerEnforcedBusinessOS.run_copilot_tool(...)`, which enforces allowlisted tool names, blocks mutations on posted journal entries, and logs every allowed or denied attempt to `CopilotAuditLog`.
- **CI Quality Gate**: GitHub Actions runs `pytest` across unit, invariant, and reconciliation parity tests on every push and pull request.

---

## Local Setup

```bash
git clone git@github.com:pra986/ledger-enforced-crm-business-os.git
cd ledger-enforced-crm-business-os
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Run CLI demo
python -m business_os.cli

# Run test suite
pytest -v
```
debits == credits) across scoped AI Copilot tools.
