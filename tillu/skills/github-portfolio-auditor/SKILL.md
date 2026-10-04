---
name: github-portfolio-auditor
description: Scan Heoster's GitHub repositories and produce a structured code-quality and portfolio-readiness report with actionable improvements.
allowed-capabilities: [web_search, webpage_read, document_search, research_context]
---

This skill runs weekly or on request. It audits Heoster's public GitHub profile and repositories without any external write operations.

## Steps

1. Search for Heoster's GitHub profile and public repository listing using the web search capability. Retrieve the list of pinned and recently active repositories.

2. For each repository (up to 10, prioritising pinned ones), read the following pages using webpage_read:
   - The README (check for: project description, setup instructions, usage examples, badges, licence, contribution guide).
   - The repository root file listing (check for: presence of .gitignore, licence file, CI config, Dockerfile or equivalent, tests directory, docs directory).
   - The most recent commit messages (check for: meaningful commit descriptions vs. generic messages like "fix" or "update").

3. Evaluate each repository against these criteria and score each 1–5:
   - **Documentation quality**: README completeness, inline comments, API docs.
   - **Project structure**: logical directory layout, separation of concerns, config files.
   - **Code hygiene**: consistent naming, no obvious debug/dead code in visible files, CI present.
   - **Showcase readiness**: live demo link or screenshot, clear problem statement, audience-appropriate description.
   - **Activity signal**: recent commits, open issues, version tags or releases.

4. Identify the top 3 repositories with the strongest portfolio potential and the top 3 that need the most improvement.

5. Produce a structured report with:
   - An overall portfolio health summary (1–2 sentences).
   - A scored table of evaluated repositories.
   - Specific, actionable improvement suggestions for the bottom 3 (e.g. "Add a README with a demo GIF", "Add a licence file", "Pin this repo to your profile").
   - Recognition of 1–2 strong points to preserve.

6. Save the report as a note using the create_note action only after showing the full report text and receiving explicit approval. Do not post or push anything to GitHub directly.

## Constraints

- Do not invent repository contents or scores. Base every assessment only on what was actually retrieved.
- If a repository page cannot be read, mark it as unreadable and skip it rather than guessing.
- Approval is required before saving the note. Never modify or create GitHub content.
- Do not include or log authentication tokens or personal access keys.
