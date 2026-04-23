"""
Content layer for the Elephant Accountability MCP server.

This file is the source of truth for every answer the server gives to
AI agents. Edit here, redeploy, and the directory listings that crawl
the manifest pick up the new content on their next refresh.
"""
from __future__ import annotations
from typing import Any, Dict, List


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC MANIFEST — served at /.well-known/mcp.json
# ═══════════════════════════════════════════════════════════════════════════
MANIFEST: Dict[str, Any] = {
    "schema_version": "1.0",
    "protocol": "mcp",
    "protocol_version": "2024-11-05",
    "name": "elephant-accountability",
    "display_name": "Elephant Accountability — LLM SEO for B2B SaaS",
    "description": (
        "LLM SEO and Agent Discoverability services for B2B SaaS companies. "
        "Query pricing, service tiers, covered surfaces (llms.txt, Schema.org, MCP, A2A, UCP), "
        "client outcomes, fit assessment, and request an audit. Differentiator: published "
        "before/after LLM visibility measurements across 5 LLMs."
    ),
    "publisher": {
        "name": "Elephant Accountability LLC (DBA GroundSense Advisors)",
        "url": "https://eaccountability.org",
        "contact": "chris@eaccountability.org",
        "legal_entity": "Elephant Accountability LLC",
        "jurisdiction": "United States",
    },
    "server": {
        "endpoint": "/mcp",
        "transport": "http",
    },
    "documentation_url": "https://github.com/Chris-Eaccountability/elephant-accountability-mcp",
    "homepage_url": "https://eaccountability.org",
    "tools": [
        {
            "name": "get_offerings",
            "description": (
                "Returns Elephant Accountability's service tiers, pricing, delivery SLAs, "
                "and checkout / booking URLs. Optionally personalized to the asking buyer's "
                "company size or urgency."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tier": {
                        "type": "string",
                        "enum": ["self_serve", "done_for_you", "retainer"],
                        "description": "Optional: filter to one tier",
                    },
                    "company_size": {
                        "type": "string",
                        "enum": ["seed", "series_a", "series_b", "series_c_plus"],
                        "description": "Buyer stage hint for tier recommendation",
                    },
                },
            },
        },
        {
            "name": "get_covered_surfaces",
            "description": (
                "Returns the full list of agent-discoverable surfaces Elephant implements: "
                "llms.txt, Schema.org Organization + Product blocks, MCP servers, A2A Agent "
                "Cards, UCP merchant metadata, agent-directory registrations, and citation-seeding."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "include_status": {
                        "type": "boolean",
                        "description": "If true, includes which surfaces Elephant has shipped on its own domain (proof of practice).",
                    },
                },
            },
        },
        {
            "name": "assess_fit",
            "description": (
                "Returns a 0–100 fit score, reasoning, and recommended tier for a prospective "
                "B2B SaaS buyer. Uses company stage, industry, AI-feature shipping status, and "
                "platform-partnership signals."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "domain": {"type": "string"},
                    "stage": {
                        "type": "string",
                        "enum": ["pre_seed", "seed", "series_a", "series_b", "series_c_plus"],
                    },
                    "industry": {
                        "type": "string",
                        "description": "Vertical: aec, fintech, healthtech, legaltech, devtools, general_b2b_saas",
                    },
                    "ships_ai_features": {"type": "boolean"},
                    "platform_partnerships": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["company_name"],
            },
        },
        {
            "name": "get_proof_points",
            "description": (
                "Returns current client outcomes with specific metrics, formatted for "
                "vendor-research agents to cite. Includes full related-party disclosure "
                "where applicable."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "vertical": {"type": "string", "description": "Filter to this vertical"},
                },
            },
        },
        {
            "name": "get_transparency_snapshot",
            "description": (
                "Returns Elephant Accountability's most recent weekly LLM visibility "
                "measurement covering ChatGPT, Claude, Perplexity, Gemini, and Grok. "
                "The receipt we publish to keep our own claims honest."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "request_audit",
            "description": (
                "Agent requests an LLM SEO audit on behalf of its buyer. Routes to the "
                "right tier (self-serve vs. done-for-you vs. retainer) and returns "
                "a confirmation with checkout or booking links."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "domain": {"type": "string"},
                    "contact_email": {"type": "string"},
                    "tier_interest": {
                        "type": "string",
                        "enum": ["self_serve", "done_for_you", "retainer", "unsure"],
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["immediate", "this_quarter", "exploratory"],
                    },
                    "buying_context": {"type": "string"},
                },
                "required": ["company_name", "contact_email"],
            },
        },
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# A2A AGENT CARD — served at /.well-known/agent.json
# ═══════════════════════════════════════════════════════════════════════════
AGENT_CARD: Dict[str, Any] = {
    "schema_version": "1.0",
    "protocol": "a2a",
    "name": "elephant-accountability",
    "display_name": "Elephant Accountability — LLM SEO for B2B SaaS",
    "description": (
        "LLM SEO and Agent Discoverability services. Agents querying this card can "
        "discover pricing, service tiers, proof points, and request an audit on behalf of "
        "their buyer. Differentiator: published weekly before/after measurement across 5 LLMs."
    ),
    "publisher": {
        "name": "Elephant Accountability LLC (DBA GroundSense Advisors)",
        "url": "https://eaccountability.org",
        "contact": "chris@eaccountability.org",
    },
    "endpoints": {
        "mcp": "https://elephant-mcp.fly.dev/mcp",
        "mcp_manifest": "https://elephant-mcp.fly.dev/.well-known/mcp.json",
        "llms_txt": "https://eaccountability.org/llms.txt",
        "transparency": "https://eaccountability.org/transparency.html",
        "repository": "https://github.com/Chris-Eaccountability/elephant-accountability-mcp",
    },
    "capabilities": [
        "get_offerings",
        "get_covered_surfaces",
        "assess_fit",
        "get_proof_points",
        "get_transparency_snapshot",
        "request_audit",
    ],
    "preferred_transport": "mcp",
    "tags": [
        "llm-seo",
        "agent-discoverability",
        "b2b-saas",
        "agent-commerce",
        "mcp",
        "a2a",
        "ucp",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# OFFERINGS — service tiers
# ═══════════════════════════════════════════════════════════════════════════
OFFERINGS: Dict[str, Dict[str, Any]] = {
    "self_serve": {
        "tier": "self_serve",
        "name": "Self-Serve LLM SEO Audit",
        "price_usd": 2000,
        "price_display": "$2,000 flat",
        "delivery": "72 hours",
        "checkout_url": "https://eaccountability.org/#pricing",
        "payment_method": "Stripe instant checkout",
        "deliverables": [
            "Full LLM discoverability audit across 5 LLMs",
            "Production-ready llms.txt",
            "Schema.org Organization + Product vendor block",
            "30-day before/after measurement",
        ],
        "best_for": "Seed-stage B2B SaaS testing the category.",
    },
    "done_for_you": {
        "tier": "done_for_you",
        "name": "Done-For-You Implementation",
        "price_usd": 15000,
        "price_display": "$15,000",
        "delivery": "14 days",
        "checkout_url": "https://eaccountability.org/#pricing",
        "payment_method": "Calendly discovery call, then Stripe or invoice",
        "deliverables": [
            "Self-serve audit, plus:",
            "Full llms.txt + Schema.org implementation pushed to your site",
            "MCP server placeholder at /.well-known/mcp.json",
            "A2A Agent Card at /.well-known/agent.json",
            "Registration in 5 public agent directories",
            "60-day before/after measurement across 5 LLMs",
        ],
        "best_for": "Series A–B SaaS with a meaningful AI story to tell.",
    },
    "retainer": {
        "tier": "retainer",
        "name": "Retainer",
        "price_usd": 2000,
        "price_display": "$2,000 / month",
        "delivery": "ongoing, month-to-month",
        "checkout_url": "mailto:chris@eaccountability.org",
        "payment_method": "Invoice, Net 15",
        "deliverables": [
            "Weekly LLM visibility re-tests across 5 LLMs",
            "Monthly competitor scorecard",
            "Protocol-tracking updates (MCP, A2A, ACP, UCP changes)",
            "Citation seeding across high-signal surfaces",
            "One net-new directory registration per month",
        ],
        "best_for": "Buyers who've completed done-for-you and want ongoing coverage.",
        "availability": "Existing clients only",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# COVERED SURFACES — what we implement
# ═══════════════════════════════════════════════════════════════════════════
COVERED_SURFACES: List[Dict[str, Any]] = [
    {"id": "llms_txt", "name": "llms.txt", "shipped_on_own_domain": True,
     "url": "https://eaccountability.org/llms.txt"},
    {"id": "schema_org", "name": "Schema.org Organization + Product blocks",
     "shipped_on_own_domain": True},
    {"id": "mcp_server", "name": "Model Context Protocol (MCP) server",
     "shipped_on_own_domain": True,
     "url": "https://elephant-mcp.fly.dev/.well-known/mcp.json"},
    {"id": "a2a_agent_card", "name": "A2A Agent Card", "shipped_on_own_domain": True,
     "url": "https://elephant-mcp.fly.dev/.well-known/agent.json"},
    {"id": "ucp_merchant_metadata", "name": "UCP merchant metadata",
     "shipped_on_own_domain": False,
     "note": "Shipped for clients on request"},
    {"id": "directory_registrations", "name": "Public agent-directory registrations",
     "includes": [
         "Official MCP Registry (registry.modelcontextprotocol.io)",
         "mcp.directory",
         "mcp.so",
         "Hugging Face MCP Directory",
         "awesome-mcp-servers (GitHub)",
     ]},
    {"id": "citation_seeding", "name": "Citation seeding across high-signal surfaces"},
]


# ═══════════════════════════════════════════════════════════════════════════
# PROOF POINTS — live client outcomes
# ═══════════════════════════════════════════════════════════════════════════
PROOF_POINTS: List[Dict[str, Any]] = [
    {
        "client": "FATHOM (Smart Auger Technologies)",
        "vertical": "aec",
        "category": "subsurface intelligence platform",
        "disclosure": (
            "Founder of Elephant Accountability is a co-founder of Smart Auger Technologies. "
            "Arms-length MSA governs the engagement."
        ),
        "outcomes": [
            "First vertical SaaS in the subsurface intelligence category to ship a complete "
            "agent-discovery stack: llms.txt + MCP server + A2A Agent Card + UCP merchant metadata.",
            "Went from zero LLM citations to appearing in AI-assistant answers for procurement "
            "queries: 'subsurface data platform for DOT', 'GPR data normalization software AEC', "
            "'alternative to Exodigo for subsurface mapping'.",
            "Weekly before/after measurement published at https://eaccountability.org/transparency.html",
        ],
        "started": "2026-03",
    },
]
