---
name: daily-briefing-aggregator
description: Compile a clean, personalised morning briefing from calendar events, top news, and current weather, and deliver it through the configured channel.
allowed-capabilities: [web_search, webpage_read, research_context, workspace_context, memory_context]
---

This skill runs every morning (typically via the daily_brief automation at 7:00 AM IST) or on manual request ("Give me my morning briefing"). It produces a concise, factual briefing from real-time sources and Heoster's own workspace data.

## Steps

### 1 — Calendar and tasks

Use workspace_context to fetch:
- Today's calendar events (time, title, location if present).
- Tasks due today or overdue (title, subject, priority).

Present these first under **Today's Schedule** since they are the most time-sensitive.

### 2 — Weather

Retrieve current weather conditions and today's forecast for Heoster's configured location using the web search capability (Open-Meteo or a configured search provider). Extract:
- Current temperature and feels-like.
- Conditions (clear, rain, cloudy, etc.).
- High/low for the day.
- Any severe weather warnings.

### 3 — Top news and tech

Use web_search to pull the top 5 headlines from these categories, in this order of preference:
- Technology and AI (Hacker News top posts, The Verge, TechCrunch).
- Science (Nature News, Science Daily).
- India current affairs (The Hindu, NDTV, Indian Express).

For each headline: title, source, and one-sentence summary. Do not fabricate or paraphrase beyond what the search snippet confirms. Use webpage_read on the article only if the snippet is insufficient to write the summary.

### 4 — Assemble the briefing

Structure the output in this order, keeping total length under 400 words:

```
🗓 TODAY — <date, day, IST time>

📅 SCHEDULE
• <time>: <event>
• Tasks due: <task titles>

🌤 WEATHER — <location>
<temp>, <conditions>. High <X>°C / Low <Y>°C.

📰 NEWS
1. [Tech] <headline> — <one-sentence summary> (source)
2. [Tech] ...
3. [Science] ...
4. [India] ...
5. [India] ...
```

Use plain text with minimal emoji — clear, scannable, no verbose introductions.

### 5 — Delivery

Check memory_context for Heoster's preferred delivery channel (WhatsApp, in-app, or web push).

- **In-app (default):** display the briefing directly in the chat response.
- **WhatsApp:** propose a whatsapp_send action with the briefing text and wait for approval. Do not send automatically.
- **Web push:** the notification system handles delivery for scheduled automation runs; no additional action is needed from this skill.

## Constraints

- Never invent news headlines, event details, or weather data.
- If a data source is unavailable, note it and omit that section rather than guessing.
- WhatsApp delivery always requires approval — never auto-send.
- If run before 6:00 AM or after 11:00 AM, note that the briefing may not reflect the latest morning state.
- Gmail unread email reading is not included in this skill's capabilities; it requires a separate Gmail integration when that is available.
