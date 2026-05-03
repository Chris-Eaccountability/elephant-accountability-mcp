"""Tests for the standalone Elephant Accountability MCP server."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app(monkeypatch, tmp_path):
    """Build a fresh app with an isolated DB per test."""
    monkeypatch.setenv("ELEPHANT_MCP_DATA_DIR", str(tmp_path))
    # Reload the server module so module-level DATA_DIR/DB_PATH pick up the new env
    import importlib
    from app import server as srv_module
    importlib.reload(srv_module)
    # Trigger startup schema init
    with TestClient(srv_module.app) as client:
        yield client


def test_root(app):
    r = app.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "Elephant Accountability" in body["service"]
    assert body["mcp_endpoint"] == "/mcp"


def test_health(app):
    r = app.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["audit_requests"] == 0
    assert body["reciprocal_calls"] == 0


def test_manifest(app):
    r = app.get("/.well-known/mcp.json")
    assert r.status_code == 200
    manifest = r.json()
    assert manifest["name"] == "elephant-accountability"
    assert manifest["protocol"] == "mcp"
    names = [t["name"] for t in manifest["tools"]]
    assert set(names) == {
        "get_offerings", "get_covered_surfaces", "assess_fit",
        "get_proof_points", "get_transparency_snapshot", "request_audit",
    }


def test_manifest_no_dba(app):
    """Brand-audit Fire 2: ensure no DBA reference leaks through MANIFEST."""
    r = app.get("/.well-known/mcp.json")
    body = json.dumps(r.json()).lower()
    assert "groundsense" not in body
    assert "dba" not in body
    assert "llm seo" not in body


def test_agent_card(app):
    r = app.get("/.well-known/agent.json")
    assert r.status_code == 200
    card = r.json()
    assert card["name"] == "elephant-accountability"
    assert card["protocol"] == "a2a"
    assert "mcp" in card["endpoints"]
    assert "repository" in card["endpoints"]


def test_agent_card_no_dba(app):
    """Brand-audit Fire 2: ensure no DBA reference leaks through AGENT_CARD."""
    r = app.get("/.well-known/agent.json")
    body = json.dumps(r.json()).lower()
    assert "groundsense" not in body
    assert "dba" not in body
    assert "llm seo" not in body


def test_llms_txt_redirects(app):
    r = app.get("/llms.txt", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "https://eaccountability.org/llms.txt"


def test_mcp_initialize(app):
    r = app.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert body["result"]["serverInfo"]["name"] == "elephant-accountability"


def test_mcp_tools_list(app):
    r = app.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    body = r.json()
    names = [t["name"] for t in body["result"]["tools"]]
    assert "get_offerings" in names
    assert "request_audit" in names


def test_mcp_get_offerings_all(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "get_offerings", "arguments": {}},
    })
    payload = json.loads(r.json()["result"]["content"][0]["text"])
    assert set(payload["offerings"].keys()) == {"self_serve", "done_for_you", "retainer"}
    # Offering names must be certification-bureau aligned (not "LLM SEO")
    assert "LLM SEO" not in payload["offerings"]["self_serve"]["name"]
    assert "EVI" in payload["offerings"]["self_serve"]["name"] or "Audit" in payload["offerings"]["self_serve"]["name"]


def test_mcp_get_offerings_seed_recommends_self_serve(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "get_offerings", "arguments": {"company_size": "seed"}},
    })
    payload = json.loads(r.json()["result"]["content"][0]["text"])
    assert payload["recommendation"] == "self_serve"


def test_mcp_assess_fit_strong(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "assess_fit", "arguments": {
            "company_name": "Acme AI",
            "stage": "series_a",
            "industry": "aec",
            "ships_ai_features": True,
            "platform_partnerships": ["esri", "autodesk"],
        }},
    })
    payload = json.loads(r.json()["result"]["content"][0]["text"])
    assert payload["fit_score"] >= 80
    assert payload["recommended_tier"] == "done_for_you"


def test_mcp_assess_fit_weak(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 6, "method": "tools/call",
        "params": {"name": "assess_fit", "arguments": {"company_name": "Random Co"}},
    })
    payload = json.loads(r.json()["result"]["content"][0]["text"])
    assert payload["fit_score"] <= 50


def test_mcp_get_proof_points(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 7, "method": "tools/call",
        "params": {"name": "get_proof_points", "arguments": {"vertical": "aec"}},
    })
    payload = json.loads(r.json()["result"]["content"][0]["text"])
    assert len(payload["proof_points"]) >= 1
    assert "FATHOM" in payload["proof_points"][0]["client"]
    assert "disclosure" in payload["proof_points"][0]


def test_mcp_get_covered_surfaces(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 8, "method": "tools/call",
        "params": {"name": "get_covered_surfaces", "arguments": {"include_status": True}},
    })
    payload = json.loads(r.json()["result"]["content"][0]["text"])
    llms = next(s for s in payload["surfaces"] if s["id"] == "llms_txt")
    assert llms["shipped_on_own_domain"] is True


def test_mcp_request_audit_persists(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 9, "method": "tools/call",
        "params": {"name": "request_audit", "arguments": {
            "company_name": "Test Buyer",
            "contact_email": "agent@testbuyer.example",
            "tier_interest": "done_for_you",
            "urgency": "this_quarter",
        }},
    })
    payload = json.loads(r.json()["result"]["content"][0]["text"])
    assert payload["status"] == "received"
    assert payload["next_step"]["action"] == "discovery_call"
    assert payload["confirmation_id"].startswith("ea-mcp-")

    # Verify health endpoint reflects it
    h = app.get("/health").json()
    assert h["audit_requests"] == 1


def test_mcp_request_audit_immediate_goes_stripe(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 10, "method": "tools/call",
        "params": {"name": "request_audit", "arguments": {
            "company_name": "Urgent Co",
            "contact_email": "urgent@example.com",
            "urgency": "immediate",
        }},
    })
    payload = json.loads(r.json()["result"]["content"][0]["text"])
    assert payload["next_step"]["action"] == "stripe_checkout"


def test_mcp_unknown_tool(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 11, "method": "tools/call",
        "params": {"name": "nonexistent", "arguments": {}},
    })
    body = r.json()
    assert body["error"]["code"] == -32601


def test_mcp_resources_list(app):
    r = app.post("/mcp", json={"jsonrpc": "2.0", "id": 12, "method": "resources/list"})
    uris = [res["uri"] for res in r.json()["result"]["resources"]]
    assert "elephant://offerings" in uris


def test_mcp_resources_read(app):
    r = app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 13, "method": "resources/read",
        "params": {"uri": "elephant://offerings"},
    })
    content = json.loads(r.json()["result"]["contents"][0]["text"])
    assert "self_serve" in content["offerings"]


def test_mcp_method_not_found(app):
    r = app.post("/mcp", json={"jsonrpc": "2.0", "id": 14, "method": "nonexistent/method"})
    assert r.json()["error"]["code"] == -32601


def test_reciprocal_calls_tracked(app):
    app.post("/mcp", json={
        "jsonrpc": "2.0", "id": 15, "method": "tools/call",
        "params": {"name": "get_offerings", "arguments": {}, "client_id": "test-client"},
    })
    h = app.get("/health").json()
    assert h["reciprocal_calls"] >= 1


def test_cors_headers(app):
    r = app.options("/mcp", headers={
        "Origin": "https://claude.ai",
        "Access-Control-Request-Method": "POST",
    })
    # Starlette's CORS returns 200 with allow-origin
    assert r.headers.get("access-control-allow-origin") == "*"
