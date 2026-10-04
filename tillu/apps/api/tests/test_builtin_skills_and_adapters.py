from pathlib import Path
from app import orchestrator  # registers read capabilities
from app.learning import parse_skill_md
from app.model_adapters import build_model_adapters
from app.search_adapters import build_search_adapters

def test_builtin_skills_are_valid_and_capability_scoped():
    root=Path(__file__).resolve().parents[3]/'skills';files=sorted(root.glob('*/SKILL.md'));assert len(files)>=4
    parsed=[parse_skill_md(x.read_text()) for x in files]
    assert len({x['name'] for x in parsed})==len(parsed)
    assert all(x['instructions'] and x['allowed_capabilities'] for x in parsed)

def test_every_configured_ai_api_has_an_explicit_adapter():
    assert set(build_model_adapters())=={'groq','openrouter','google','cloudflare'}
    assert set(build_search_adapters())=={'parallel','you','tavily','firecrawl'}
