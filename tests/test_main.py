import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
from main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_shorten_valid_url():
    res = client.post("/shorten", json={"url": "https://www.google.com"})
    assert res.status_code == 200
    data = res.json()
    assert "short_code" in data
    assert len(data["short_code"]) == 7

def test_shorten_invalid_url():
    res = client.post("/shorten", json={"url": "not-a-url"})
    assert res.status_code == 422

def test_redirect():
    shorten_res = client.post("/shorten", json={"url": "https://github.com"})
    code = shorten_res.json()["short_code"]
    res = client.get(f"/r/{code}", follow_redirects=False)
    assert res.status_code == 307

def test_redirect_not_found():
    res = client.get("/r/aaaaaaa")
    assert res.status_code == 404

def test_list_urls():
    client.post("/shorten", json={"url": "https://example.com"})
    res = client.get("/urls")
    assert res.status_code == 200
    assert res.json()["count"] >= 1

def test_metrics_endpoint():
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "http_requests_total" in res.text
