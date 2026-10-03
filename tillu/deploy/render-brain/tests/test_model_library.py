import asyncio
from app.model_library import build_library,CURATED,SOURCES
from app.providers import gateway


def test_curated_library_has_free_default_for_every_provider():
    providers={'groq','cerebras','openrouter','cloudflare','google'}
    assert {x['provider'] for x in CURATED}==providers
    rows=asyncio.run(build_library(False))['models']
    assert all(x['source'].startswith('https://') for x in rows)
    assert all(any(x['provider']==p and x['free_tier'] is True for x in rows) for p in providers)
    assert set(SOURCES)==providers


def test_gateway_defaults_exist_in_curated_library():
    ids={(x['provider'],x['id']) for x in CURATED}
    for provider in gateway.providers():
        assert (provider.id,provider.model) in ids


def test_library_does_not_claim_unconfigured_models_callable():
    data=asyncio.run(build_library(False))
    for model in data['models']:
        if not model['configured']:
            assert model['live_discovered'] is False
