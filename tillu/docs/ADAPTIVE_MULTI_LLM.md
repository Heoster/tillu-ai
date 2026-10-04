# TILLU Adaptive Multi-LLM Agent Cycle

TILLU executes chat through a bounded LangGraph cycle: intent detection, planning, tool execution, context assembly, evidence evaluation, optional replanning (maximum two revisions), response synthesis and deterministic citation verification. Each model phase requests the cheapest currently available model with the required capability. If no provider is available, deterministic intent, planning, evidence and structured-output fallbacks keep supported tools operational.

## Routing score
Candidates are filtered by phase, capabilities, configuration, circuit state, predicted RPM headroom, and predicted TPM headroom. Remaining candidates are sorted using relative cost, latency EWMA, failure count, and reasoning suitability.

## 429 and failure behavior
The gateway records 60-second request/token windows. It reserves RPM and TPM headroom rather than using the published limit fully. HTTP 429 honors `Retry-After` when numeric and removes that provider from routing until cooldown ends. HTTP 5xx, timeouts, and repeated failures open an exponential circuit breaker. Responses over 5 seconds trigger fallback when another candidate exists.

## Safety boundary
Models may classify and propose registered read tools. The server validates tool names and arguments, and only the authoritative registry executes them. Write and external actions remain typed, persisted approval proposals. Models never directly execute writes.

## Honest limitation
No router can completely eliminate downtime: all configured providers can be unavailable simultaneously, credentials and quotas can expire, and networks can fail. TILLU reduces outage probability and retains deterministic support for known local tools, but free-form synthesis still requires at least one healthy model.
