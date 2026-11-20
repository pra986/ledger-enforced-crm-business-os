# Ledger-Enforced CRM Business OS Architecture

## Overview
The Ledger-Enforced CRM Business OS unifies CRM pipeline management, quote-to-invoice provenance, double-entry general ledger accounting, and scoped AI Copilot execution under a single deterministic engine (`LedgerEnforcedBusinessOS`).

## Core Invariants
1. **Stage-to-Probability Synchronization**: Every `DealRecord` enforces deterministic probability mapping via `STAGE_PROBABILITIES` (`prospecting`: 0.10, `qualified`: 0.30, `proposal`: 0.60, `negotiation`: 0.80, `closed_won`: 1.00, `closed_lost`: 0.00).
2. **Foreign-Key Quote-to-Invoice Provenance**: Every `QuoteInvoiceLink` references an existing `deal_id` and records `quote_id`, `invoice_id`, `amount_cents`, and lifecycle `status` (`quoted` -> `invoiced` -> `paid`).
3. **Double-Entry Zero-Drift Ledger**: Every `JournalEntry` operates in integer cents, enforces single-sided `JournalLine` entries (`debit_cents` XOR `credit_cents`), and requires `total_debits == total_credits > 0` before posting.
4. **Posted Journal Immutability**: Once `JournalEntry.posted` is `True`, the entry is frozen and cannot be mutated or overwritten by users or AI Copilot tools.
5. **CRM vs. Trial Balance Parity**: Unified revenue reporting reconciles invoiced/paid CRM totals directly against posted Revenue (`4000`) and Accounts Receivable (`1200`) / Cash (`1000`) trial balance totals.
6. **Audited Scoped AI Copilot**: `run_copilot_tool(...)` restricts execution to allowlisted tools (`read_pipeline`, `draft_quote`, `post_journal_entry`), blocks mutations on posted journal entries, and appends every allowed or denied attempt to `CopilotAuditLog`.
