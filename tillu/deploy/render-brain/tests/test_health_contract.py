from fastapi.testclient import TestClient
from app.main import app

def test_health_contract_exposes_role_without_secrets():
    with TestClient(app) as client:
        identity=client.get('/api/health');live=client.get('/api/health/live');ready=client.get('/api/health/ready')
    assert identity.status_code==200 and identity.json()['role'] in {'brain','runtime'}
    assert live.status_code==200 and live.json()['status']=='alive'
    assert ready.status_code in {200,503}
    text=identity.text+live.text+ready.text
    assert 'service_role_key' not in text.lower() and 'internal_secret' not in text.lower()
