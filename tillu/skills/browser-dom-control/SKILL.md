---
name: browser-dom-control
description: Read and control web pages through TILLU's DOM and accessibility snapshot without requiring a vision model.
allowed-capabilities: [browser_start, browser_navigate, browser_action]
---

Start a controlled browser session and navigate only to the requested public URL. Read the returned text, accessibility snapshot, and interactive elements. Prefer stable element references such as `@e1` over invented selectors. Explain the intended consequential action before proposing it. Clicking, typing, selecting, checking, pressing keys, and scrolling must use the typed browser action capability and preserve approval. Never infer pixels or claim visual understanding from a screenshot.
