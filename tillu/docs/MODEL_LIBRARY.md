# TILLU free/free-tier model library

Updated: 2026-10-01

TILLU keeps the complete documented Groq and Cerebras shared catalogs as curated entries and can discover the full live catalogs from every configured provider. OpenRouter's public catalog can refresh even before an API key is configured. A model is shown as **configured** only when the required private key/account setting exists. Free tiers remain quota- and availability-controlled by each provider.

## Defaults

| Provider | Default | Role |
|---|---|---|
| Groq | `openai/gpt-oss-20b` | fast intent, structured planning, execution |
| Cerebras | `gpt-oss-120b` | high-speed reasoning fallback |
| OpenRouter | `openrouter/free` | dynamic free-model fallback |
| Cloudflare Workers AI | `@cf/qwen/qwen3-30b-a3b-fp8` | edge/free-allocation fallback |
| Google Gemini | `gemini-3.1-flash-lite` | long-context, tools, multimodal reasoning |

## Official sources reviewed

- Groq supported models: https://console.groq.com/docs/models
- Groq rate limits: https://console.groq.com/docs/rate-limits
- Cerebras pricing/free tier: https://inference-docs.cerebras.ai/support/pricing
- OpenRouter free router: https://openrouter.ai/docs/guides/routing/routers/free-router
- OpenRouter model variants: https://openrouter.ai/docs/projects/docs/guides/routing/model-variants/overview
- Cloudflare Workers AI pricing/free allocation: https://developers.cloudflare.com/workers-ai/platform/pricing/
- Cloudflare model-search API: https://developers.cloudflare.com/api/resources/ai/subresources/models/methods/list/
- Google model documentation: https://ai.google.dev/gemini-api/docs/models
- Google rate limits: https://ai.google.dev/gemini-api/docs/rate-limits

## Runtime behavior

- `GET /api/models/library` returns curated entries.
- `GET /api/models/library?refresh=true` queries live catalogs only for configured providers.
- Live OpenRouter discovery imports the full model catalog and marks zero-priced or `:free` variants as free.
- Discovery failures do not silently remove curated fallbacks.
- Provider credentials are never returned to the frontend.
- The adaptive gateway still applies phase capability, health, latency, quota, cooldown, and circuit-breaker policy.

The adaptive runtime currently routes across a 13-model free/free-tier chat pool (five Groq, two Cerebras, two Cloudflare, three Gemini—including `gemini-2.5-flash`—and OpenRouter's free router), while the UI library displays the broader discovered catalog. Non-chat models such as Whisper, Orpheus, and safety guards remain cataloged for future typed audio/safety capabilities rather than being sent ordinary chat prompts.

Runtime verification without private keys discovered 481 catalog entries through the public OpenRouter catalog plus curated provider records, including 38 currently marked free. Counts change as providers update catalogs.

The library is informational and operational metadata, not a promise of permanent free access. Provider model availability and quotas can change.
