---
name: exam-resource-fetcher
description: Find and surface official PYQ PDFs and study resources for Class 12 board subjects from trusted public education portals.
allowed-capabilities: [web_search, webpage_read, document_search, research_context, syllabus_context]
---

This skill runs when Heoster requests previous year question papers (PYQs) or official study resources for a specific subject and year (e.g. "Get 2024 Physics PYQs", "Find Class 12 Chemistry CBSE sample papers").

## Steps

1. Parse the request to identify:
   - **Subject**: Physics, Chemistry, Mathematics, Biology, Computer Science, English, etc.
   - **Year(s)**: specific year or a range (default: last 3 years if unspecified).
   - **Exam board**: CBSE (default), ISC, or state board if mentioned.
   - **Resource type**: PYQ (previous year question paper), sample paper, marking scheme, or syllabus PDF.

2. Search for the resource on trusted official sources only, in this priority order:
   - cbse.gov.in (CBSE official portal)
   - cbseacademic.nic.in (CBSE academic portal)
   - bsiepunjab.ac.in / mahahsscboard.in or equivalent state board sites if applicable
   - ncert.nic.in for textbook PDFs

   Use web_search with targeted queries such as:
   `site:cbse.gov.in Class 12 Physics question paper 2024 PDF`

3. For each search result, use webpage_read to verify:
   - The page is on the expected official domain.
   - The linked PDF matches the requested subject, year, and paper type (confirm from page text; do not guess from URL alone).
   - The direct PDF download URL is present.

4. Check TILLU's knowledge base using document_search to see if any of these PDFs have already been indexed locally.

5. Present Heoster with:
   - A clean list of found resources: subject, year, paper type, source domain, and the direct PDF link.
   - A note on any years or paper types that could not be found on official sources.
   - A suggestion to index the PDFs in TILLU's knowledge base for offline search — propose the index_file action for each PDF and wait for approval before indexing.

6. Do not download or index anything without approval. Do not use unofficial third-party sites (coaching portals, question-bank aggregators) unless official sources are confirmed unavailable and Heoster explicitly asks.

## Constraints

- Only use official government or board-authorised domains as primary sources.
- If a PDF link cannot be verified as legitimate, report it as unverified and do not present it as confirmed.
- Never auto-download or store files. Indexing requires explicit approval per file.
- Check TILLU's syllabus context to align fetched resources with tracked subjects when available.
