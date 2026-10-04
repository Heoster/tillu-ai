from fastapi.testclient import TestClient
from app.main import app


def test_chat_sse_emits_status_and_authoritative_final():
    with TestClient(app) as client:
        with client.stream('POST','/api/chat/stream',json={'message':'calculate 2+2'}) as response:
            body=''.join(response.iter_text())
    assert response.status_code==200
    assert response.headers['content-type'].startswith('text/event-stream')
    assert 'event: status' in body
    assert 'event: final' in body
    assert 'event: done' in body
    assert '"conversation_id"' in body
