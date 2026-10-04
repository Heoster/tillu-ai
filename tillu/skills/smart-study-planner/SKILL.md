---
name: smart-study-planner
description: Break a syllabus or exam date sheet into a realistic day-by-day study schedule, create calendar events and tasks, and generate topic flashcard prompts for upcoming sessions.
allowed-capabilities: [syllabus_context, workspace_context, document_search, memory_context]
---

This skill activates when Heoster uploads a syllabus PDF or exam date sheet, or asks to plan study sessions for an upcoming exam. It reads tracked progress before planning and never overwrites existing confirmed study events without approval.

## Steps

### Phase 1 — Gather context

1. Use document_search to read the uploaded syllabus or exam date sheet. Extract:
   - Subject names and chapters/topics per subject.
   - Exam dates and their day-of-week positions.
   - Any weightage or marking scheme clues.

2. Use syllabus_context to retrieve the currently tracked syllabus, completed topics, confidence levels, and pending items for each subject.

3. Use workspace_context to check:
   - Existing study tasks and their due dates.
   - Upcoming calendar events (to avoid double-booking).
   - Recent activity to understand current pace.

4. Use memory_context to check if Heoster has stated study time preferences (e.g. "I study best in the morning", "max 3 hours per day", "no study on Sundays").

### Phase 2 — Build the plan

5. Calculate the number of study days available between today and each exam date. Reserve the day before each exam for revision and rest. Deduct already-booked calendar blocks.

6. Assign chapters and topics to specific days using this logic:
   - Harder or lower-confidence topics first (early in the window).
   - Interleave subjects to avoid fatigue (no more than 2 consecutive days on the same subject).
   - Respect stated daily time limits; default to a maximum of 3 hours/day across subjects.
   - Leave at least one buffer day per week for catch-up.

7. For each planned session, state: date, subject, chapter(s) and topic(s), estimated duration, and session goal (first read, revision, practice, or mock test).

### Phase 3 — Propose actions

8. Present the complete day-by-day plan in a clean table before proposing any actions.

9. Propose the following approval-gated actions — one approval covers all items of the same type, but show the full list first:
   - A create_event action for each study session (title: "Study: [Subject] – [Topic]", with the session duration as end_at, reminder 30 minutes before).
   - A create_task action for each chapter (title: "Complete [Chapter]", subject, due date set to the last session day for that chapter).

10. Generate 3–5 flashcard-style question prompts for the first upcoming study topic and present them in the response. These are text prompts only — not saved unless Heoster asks.

### Phase 4 — Confirm and adjust

11. After Heoster approves or adjusts, confirm how many events and tasks were created. Note any topics that could not be fit into the window and suggest either reducing scope or adding extra hours.

## Constraints

- Never create tasks or calendar events without explicit approval.
- Do not mark any topic as studied or confident without Heoster confirming it.
- If the exam date has already passed, say so rather than building a plan for it.
- Base all assumptions (study hours, pace) on stated preferences or sensible defaults — never infer from device activity.
- Flashcard prompts are read-only output. Saving them as notes requires a separate approval.
