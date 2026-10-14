import asyncio
import json
import httpx
import pytest
from app import ai


def test_groq_request_and_json(monkeypatch):
    monkeypatch.setattr(ai.settings, 'ai_provider', 'groq')
    monkeypatch.setattr(ai.settings, 'groq_api_key', 'test-only')
    original = httpx.AsyncClient
    def handler(request):
        assert request.url.host == 'api.groq.com'
        assert request.headers['authorization'] == 'Bearer test-only'
        body=json.loads(request.content)
        assert body['response_format'] == {'type':'json_object'}
        assert body['messages'][1]['content'] == '{"answer": "example"}'
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]})
    monkeypatch.setattr(ai.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler),**kwargs))
    assert asyncio.run(ai.generate_json('Return JSON', {'answer':'example'})) == {'ok':True}


def test_missing_groq_key_does_not_use_local_marks(monkeypatch):
    monkeypatch.setattr(ai.settings,'ai_provider','groq')
    monkeypatch.setattr(ai.settings,'groq_api_key','')
    assert asyncio.run(ai.evaluate({},'My answer'))['status']=='unavailable'


def test_groq_rate_limit_propagates(monkeypatch):
    monkeypatch.setattr(ai.settings,'ai_provider','groq')
    monkeypatch.setattr(ai.settings,'groq_api_key','test-only')
    original=httpx.AsyncClient
    monkeypatch.setattr(ai.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(lambda request:httpx.Response(429)),**kwargs))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(ai.generate_json('Return JSON',{}))
