---
name: expense-tracker
description: Parse a pasted or forwarded expense receipt or invoice and produce a structured expense entry for Heoster's review and optional saving as a note.
allowed-capabilities: [web_search, webpage_read, document_search, research_context, workspace_context]
---

This skill activates when Heoster pastes or forwards a receipt text, shares a screenshot description of an invoice, or asks "log this expense" and provides receipt details. It parses the expense, classifies it, and prepares a structured entry.

## Steps

### 1 — Extract expense fields

Parse the provided text, email body, or uploaded document for:
- **Merchant / Payee**: business or person paid.
- **Date**: transaction date (use today's date if absent, and note the assumption).
- **Amount**: total paid, including currency symbol (default ₹ for Indian transactions).
- **Category**: classify into one of:
  - Food & Dining, Transportation, Education & Books, Technology & Software, Shopping, Utilities & Bills, Healthcare, Entertainment, Subscriptions, Miscellaneous.
- **Payment method**: UPI, card, cash, net banking — if inferable from the text.
- **Description**: a short note about what was purchased (1 sentence max).
- **GST / tax amount**: if separately stated.

If a required field (merchant, amount) cannot be determined from the provided text, ask Heoster to clarify rather than guessing.

### 2 — Validate and confirm

Present the parsed entry in a clean, human-readable format before any save action:

```
💳 EXPENSE ENTRY
Date:          <date>
Merchant:      <name>
Amount:        ₹<amount>
Category:      <category>
Payment:       <method or "not specified">
Description:   <brief description>
GST:           ₹<gst or "not stated">
```

Ask: "Does this look right? I'll save it as a note when you confirm."

### 3 — Save as a note

Only after explicit confirmation, propose a create_note action with:
- Title: `Expense: <Merchant> – <Date>`
- Content: the formatted entry above plus a running monthly total note if previous expense notes exist in the workspace.

Check workspace_context for existing expense notes for the current month. If found, add a line showing the updated month-to-date total.

### 4 — Category trends (optional)

If Heoster asks "show my spending this month" or similar, use document_search to retrieve all expense notes from the current month. Summarise total spend by category. Present as a simple breakdown — do not create charts or external files.

## Constraints

- Do not connect to Google Sheets, bank APIs, or any external service. This skill is notes-based only.
- Never infer amounts or merchant names. If ambiguous, ask.
- All saving is approval-gated. Do not create notes silently.
- Do not store full card numbers, UPI IDs, or account numbers — redact them from the note content (show last 4 digits only if present).
- Tax calculations or investment advice are outside scope. State that clearly if asked.
