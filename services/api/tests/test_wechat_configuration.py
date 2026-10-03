import logging
import httpx
import pytest
from fastapi import HTTPException
from yeats.wechat import Wechat
from yeats.config import settings

def test_transport_logs_disabled():
    assert logging.getLogger('httpx').disabled
    assert logging.getLogger('httpcore').disabled

def test_network_errors_never_expose_secret_url(monkeypatch):
    monkeypatch.setattr(settings,'wechat_appid','wx-contract-only')
    monkeypatch.setattr(settings,'wechat_secret','synthetic-sensitive-value')
    def fail(*args,**kwargs):
        raise httpx.ConnectError('https://example.invalid/?secret=synthetic-sensitive-value')
    monkeypatch.setattr(httpx.Client,'request',fail)
    with pytest.raises(HTTPException) as result:
        Wechat().identity('synthetic-invalid-code')
    assert result.value.status_code==502
    assert 'synthetic-sensitive-value' not in str(result.value)
    assert result.value.__suppress_context__
