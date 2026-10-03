from app.production_readiness import report

def test_readiness_is_truthful_and_migrations_present():
    result=report()
    assert result['checks']['all_migrations_present'] is True
    assert all(result['migrations'].values())
    assert result['verification']['rls']=='not_tested'
    assert result['verification']['cron']=='not_tested'
    assert result['integrations']['honcho_configured'] is False
