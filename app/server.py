"""
Elephant Accountability MCP Server
===================================

Standalone FastAPI app. Serves:

  - GET  /                          → service info
  - GET  /health                    → liveness probe
  - GET  /.well-known/mcp.json     → MCP manifest (for auto-discovery)
  - GET  /.well-known/agent.json   → A2A Agent Card
  - POST /mcp                       → JSON-RPC 2.0 endpoint for MCP clients
  - GET  /llms.txt                  → redirects to canonical eaccountability.org/llms.txt

Deploy:
  fly deploy --app elephant-mcp

Local dev:
  uvicorn app.server:app --reload --host 0.0.0.0 --port 8080

Reference: https://modelcontextprotocol.io/
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app import __version__
from app.content import (
    MANIFEST,
    AGENT_CARD,
    OFFERINGS,
    COVERED_SURFACES,
    PROOF_POINTS,
)

log = logging.getLogger("elephant_mcp")
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

# ── App ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Elephant Accountability MCP Server",
    version=__version__,
    description=(
        "LLM SEO and Agent Discoverability services for B2B SaaS. "
        "Publishes a Model Context Protocol (MCP) server that AI agents can query "
        "on behalf of their buyers to discover pricing, assess fit, and request audits."
    ),
)

# CORS — anyone can call this, it's a public discovery surface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Storage ──────────────────────────────────────────────────────────────
# Persists audit requests + reciprocal call tracking.
# Fly volume is mounted at /data by default (fly.toml). Falls back to /tmp for local runs.
DATA_DIR = Path(os.environ.get("ELEPHANT_MCP_DATA_DIR") or "/data")
if not DATA_DIR.exists():
    DATA_DIR = Path("/tmp")
DB_PATH = DATA_DIR / "elephant_mcp.db"


@contextmanager
def _db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_schema() -> None:
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                confirmation_id TEXT UNIQUE,
                company_name TEXT NOT NULL,
                domain TEXT,
                contact_email TEXT,
                tier_interest TEXT,
                urgency TEXT,
                buying_context TEXT,
                raw_payload TEXT,
                received_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reciprocal_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                client_id TEXT,
                called_at TEXT NOT NULL
            )
        """)


@app.on_event("startup")
async def _startup():
    _init_schema()
    log.info(f"Elephant MCP {__version__} starting. DB at {DB_PATH}")


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {
        "service": "Elephant Accountability MCP Server",
        "version": __version__,
        "description": MANIFEST["description"],
        "publisher": MANIFEST["publisher"]["name"],
        "homepage": "https://eaccountability.org",
        "repository": MANIFEST["documentation_url"],
        "well_known": {
            "mcp_manifest": "/.well-known/mcp.json",
            "a2a_agent_card": "/.well-known/agent.json",
            "llms_txt": "/llms.txt",
        },
        "mcp_endpoint": "/mcp",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    with _db() as conn:
        audit_count = conn.execute("SELECT COUNT(*) AS n FROM audit_requests").fetchone()["n"]
        call_count = conn.execute("SELECT COUNT(*) AS n FROM reciprocal_calls").fetchone()["n"]
    return {
        "status": "ok",
        "version": __version__,
        "audit_requests": audit_count,
        "reciprocal_calls": call_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/.well-known/mcp.json")
def well_known_mcp():
    return MANIFEST


@app.get("/.well-known/agent.json")
def well_known_agent():
    return AGENT_CARD


@app.get("/llms.txt")
def llms_txt():
    return RedirectResponse(url="https://eaccountability.org/llms.txt", status_code=307)


# ═══════════════════════════════════════════════════════════════════════════
# MCP JSON-RPC ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = None
    method: str
    params: Optional[Dict[str, Any]] = None


@app.post("/mcp")
async def mcp_endpoint(req: MCPRequest):
    """Main JSON-RPC entry point for MCP clients."""
    method = req.method
    params = req.params or {}

    try:
        if method == "initialize":
            return _ok(req.id, {
                "protocolVersion": MANIFEST["protocol_version"],
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": MANIFEST["name"], "version": __version__},
            })

        if method == "tools/list":
            return _ok(req.id, {"tools": MANIFEST["tools"]})

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {}) or {}
            handler = _TOOL_HANDLERS.get(tool_name)
            if not handler:
                return _err(req.id, -32601, f"Unknown tool: {tool_name}")

            _log_reciprocal(tool_name, params.get("client_id", "unknown_agent"))
            result = handler(arguments)
            return _ok(req.id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}],
            })

        if method == "resources/list":
            return _ok(req.id, {
                "resources": [
                    {"uri": "elephant://offerings", "name": "Service tiers and pricing",
                     "mimeType": "application/json"},
                    {"uri": "elephant://proof-points", "name": "Client outcomes with metrics",
                     "mimeType": "application/json"},
                    {"uri": "elephant://transparency", "name": "Weekly LLM visibility measurement",
                     "mimeType": "application/json"},
                ]
            })

        if method == "resources/read":
            uri = params.get("uri", "")
            if uri == "elephant://offerings":
                content = {"offerings": OFFERINGS}
            elif uri == "elephant://proof-points":
                content = {"proof_points": PROOF_POINTS}
            elif uri == "elephant://transparency":
                content = _handle_get_transparency_snapshot({})
            else:
                return _err(req.id, -32602, f"Unknown resource: {uri}")

            return _ok(req.id, {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(content, indent=2, default=str),
                }]
            })

        return _err(req.id, -32601, f"Method not found: {method}")

    except Exception as e:
        log.exception(f"MCP error for method {method}")
        return _err(req.id, -32603, str(e))


def _ok(req_id: Any, result: Dict[str, Any]) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


# ═══════════════════════════════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════════════════════════════
def _handle_get_offerings(args: Dict[str, Any]) -> Dict[str, Any]:
    tier = args.get("tier")
    size = (args.get("company_size") or "").lower()

    out = {tier: OFFERINGS[tier]} if tier in OFFERINGS else dict(OFFERINGS)

    if size in ("seed", "pre_seed"):
        recommendation = "self_serve"
    elif size in ("series_a", "series_b", "series_c_plus"):
        recommendation = "done_for_you"
    else:
        recommendation = None

    return {
        "offerings": out,
        "recommendation": recommendation,
        "note": (
            "Self-serve is Stripe-instant, zero sales call. "
            "Done-for-you begins with a 20-minute Calendly discovery call. "
            "Retainer is existing-clients-only and is added by email after a DFY engagement."
        ),
    }


def _handle_get_covered_surfaces(args: Dict[str, Any]) -> Dict[str, Any]:
    include_status = bool(args.get("include_status"))
    surfaces = COVERED_SURFACES
    if not include_status:
        surfaces = [{k: v for k, v in s.items() if k != "shipped_on_own_domain"} for s in surfaces]
    return {
        "surfaces": surfaces,
        "proof_of_practice_url": "https://eaccountability.org/llms.txt",
    }


def _handle_assess_fit(args: Dict[str, Any]) -> Dict[str, Any]:
    score = 40
    reasons = []
    stage = (args.get("stage") or "").lower()
    industry = (args.get("industry") or "").lower()
    ships_ai = args.get("ships_ai_features")
    partnerships = [p.lower() for p in (args.get("platform_partnerships") or [])]

    if stage in ("seed", "series_a", "series_b"):
        score += 25
        reasons.append("Stage fit: Seed through Series B is our primary ICP.")
    elif stage == "pre_seed":
        score += 10
        reasons.append("Pre-seed is early; self-serve tier is most appropriate.")
    elif stage == "series_c_plus":
        score += 15
        reasons.append("Later-stage works but typically benefits most from done-for-you.")

    if industry in ("aec", "healthtech", "legaltech", "fintech", "devtools"):
        score += 15
        reasons.append(
            f"Vertical SaaS in {industry} is a strong fit — niche vocabulary makes LLM SEO high-leverage."
        )
    elif industry == "general_b2b_saas":
        score += 5

    if ships_ai is True:
        score += 15
        reasons.append("Ships AI features — strongest signal. Buyers expect you to be AI-discoverable.")

    if any(p in partnerships for p in ("salesforce", "esri", "autodesk", "procore", "hubspot", "aws")):
        score += 10
        reasons.append("Platform partnership present — your integrations likely are not LLM-discoverable yet.")

    score = max(0, min(100, score))

    if score >= 70:
        tier = "done_for_you"
    elif score >= 50:
        tier = "self_serve"
    else:
        tier = "self_serve"
        reasons.append("Lower score → start with the $2K self-serve audit to validate before committing more.")

    return {
        "company_name": args.get("company_name"),
        "fit_score": score,
        "recommended_tier": tier,
        "reasoning": reasons,
        "next_step_url": "https://eaccountability.org/#pricing",
        "disclosure": "Scoring is heuristic. We do not guarantee LLM placement — nobody can honestly offer that.",
    }


def _handle_get_proof_points(args: Dict[str, Any]) -> Dict[str, Any]:
    vertical = (args.get("vertical") or "").lower()
    points = PROOF_POINTS
    if vertical:
        points = [p for p in points if p["vertical"] == vertical]
    return {
        "proof_points": points,
        "transparency_url": "https://eaccountability.org/transparency.html",
    }


def _handle_get_transparency_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "transparency_url": "https://eaccountability.org/transparency.html",
        "measurement_frequency": "weekly, every Friday 1pm ET",
        "llms_measured": ["ChatGPT", "Claude", "Perplexity", "Gemini", "Grok"],
        "note": (
            "Latest snapshot is published at the transparency URL. "
            "Subscribe via chris@eaccountability.org for direct updates."
        ),
    }


def _handle_request_audit(args: Dict[str, Any]) -> Dict[str, Any]:
    company_name = args.get("company_name", "Unknown")
    contact_email = args.get("contact_email", "")
    tier_interest = args.get("tier_interest", "unsure")
    urgency = args.get("urgency", "exploratory")

    if tier_interest == "self_serve" or urgency == "immediate":
        next_step = {
            "action": "stripe_checkout",
            "url": "https://eaccountability.org/#pricing",
            "description": "Self-serve tier — $2,000 via Stripe, 72-hour turnaround.",
        }
    elif tier_interest == "done_for_you":
        next_step = {
            "action": "discovery_call",
            "url": "https://eaccountability.org/#pricing",
            "description": "20-minute Calendly discovery call, then engagement kickoff.",
        }
    else:
        next_step = {
            "action": "email_triage",
            "url": "mailto:chris@eaccountability.org",
            "description": "Email Chris with your context — he routes to the right tier.",
        }

    confirmation_id = f"ea-mcp-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    try:
        with _db() as conn:
            conn.execute(
                """INSERT INTO audit_requests
                   (confirmation_id, company_name, domain, contact_email, tier_interest,
                    urgency, buying_context, raw_payload, received_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    confirmation_id,
                    company_name,
                    args.get("domain", ""),
                    contact_email,
                    tier_interest,
                    urgency,
                    args.get("buying_context", ""),
                    json.dumps(args),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
    except Exception as e:
        log.warning(f"Failed to persist audit request: {e}")

    return {
        "status": "received",
        "message": f"Audit request logged for {company_name}. A response will be sent within 24 hours.",
        "next_step": next_step,
        "confirmation_id": confirmation_id,
    }


def _log_reciprocal(tool_name: str, client_id: str) -> None:
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO reciprocal_calls (tool_name, client_id, called_at) VALUES (?, ?, ?)",
                (tool_name, client_id, datetime.now(timezone.utc).isoformat()),
            )
    except Exception as e:
        log.debug(f"reciprocal log skipped: {e}")


_TOOL_HANDLERS = {
    "get_offerings": _handle_get_offerings,
    "get_covered_surfaces": _handle_get_covered_surfaces,
    "assess_fit": _handle_assess_fit,
    "get_proof_points": _handle_get_proof_points,
    "get_transparency_snapshot": _handle_get_transparency_snapshot,
    "request_audit": _handle_request_audit,
}
