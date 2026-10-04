---
name: auto-issue-responder
description: Read a new GitHub issue, check the relevant codebase context and existing issues, and draft a polite, accurate initial response or label suggestion for Heoster's review.
allowed-capabilities: [web_search, webpage_read, document_search, research_context]
---

This skill activates when Heoster forwards a new GitHub issue URL or pastes the issue title and body into chat.

## Steps

1. Read the issue page using webpage_read to extract:
   - Issue title, body, reporter, labels, and any existing comments.
   - The repository name and language.

2. Search the repository's open and recently closed issues for duplicates or related discussions using web_search (query: `site:github.com/<repo>/issues <key terms from the issue>`).

3. Read the relevant source files or documentation to understand whether the reported behaviour is a known limitation, a real bug, or a misuse. Use document_search if the repository's docs are already indexed in TILLU's knowledge base.

4. Classify the issue into one of:
   - **Bug** — reproducible, unintended behaviour with clear steps.
   - **Feature request** — new capability being asked for.
   - **Question / support** — user needs help using the project.
   - **Duplicate** — matches an existing open or closed issue.
   - **Out of scope** — does not fit the project's stated purpose.

5. Draft a response that:
   - Thanks the reporter by name.
   - Acknowledges the issue clearly and states the classification.
   - For bugs: asks for the minimal reproduction steps, environment, and version if not provided; or confirms the bug and describes where the fix would live.
   - For features: explains whether it aligns with the project direction and what the implementation approach would be, or politely declines with a reason.
   - For duplicates: links to the original issue.
   - For questions: answers using only the retrieved codebase and docs evidence.
   - Suggests one or two appropriate labels (e.g. `bug`, `enhancement`, `question`, `duplicate`, `wontfix`).
   - Stays under 250 words and does not make commitments on timelines.

6. Present the full draft to Heoster for review. Post nothing without explicit approval.

## Constraints

- Do not fabricate code fixes or claim the issue is resolved before a fix exists.
- Do not invent project policies. Base the response only on what is in the codebase and docs.
- Never post the response automatically. Always require approval.
- If the issue page cannot be read, report that and ask Heoster to paste the issue text directly.
