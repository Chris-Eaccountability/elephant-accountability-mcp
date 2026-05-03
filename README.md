# Elephant Accountability MCP Server

MCP server for the Elephant Accountability certification bureau. Surfaces vendor offerings, methodology, and audit requests to AI agents over the Model Context Protocol.

**Live endpoint:** https://elephant-mcp.fly.dev/mcp
**Manifest:** https://elephant-mcp.fly.dev/.well-known/mcp.json
**A2A Agent Card:** https://elephant-mcp.fly.dev/.well-known/agent.json
**Homepage:** https://eaccountability.org

## What this server does

When an AI agent (Claude, ChatGPT, a custom LangChain agent, etc.) needs to evaluate Elephant Accountability against the EVI v0.9 standard or surface its audit tiers to a buyer, it queries this server instead of scraping a website.

Six tools are exposed:

| Tool | Purpose |
|------|---------|
| `get_offerings` | Audit and engagement tiers (self-serve, done-for-you, retainer) with delivery SLAs and pointers to /get-started for canonical pricing |
| `get_covered_surfaces` | The agent-discoverable surfaces measured by EVI v0.9: llms.txt, Schema.org, MCP, A2A, .well-known/agent.json, UCP, structured pricing, directory registrations |
| `assess_fit` | 0–100 fit score for a buyer's company across stage, vertical, AI features, platform partnerships |
| `get_proof_points` | Live client outcomes with metrics (includes related-party disclosures) |
| `get_transparency_snapshot` | Weekly LLM visibility measurements across 5 LLMs |
| `request_audit` | Agent-initiated audit requests; routed to Stripe, Calendly, or email triage |

Two resources are exposed via `resources/list`: `elephant://offerings`, `elephant://proof-points`, `elephant://transparency`.

## Why you'd use this

- You're building a procurement agent and want to query Elephant Accountability's audit tiers and EVI v0.9 methodology directly.
- You're at Claude Desktop / Cursor / any MCP-compatible client and want direct access to Elephant's offerings + fit assessment.
- You're a competitor studying how to deploy your own MCP server — this repo is MIT-licensed, clone freely.

## Quickstart — local development

```bash
git clone https://github.com/Chris-Eaccountability/elephant-accountability-mcp.git
cd elephant-accountability-mcp

python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Run the server
uvicorn app.server:app --reload --host 0.0.0.0 --port 8080

# In another terminal, hit it
curl http://localhost:8080/.well-known/mcp.json
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0", "id":1, "method":"tools/list"}' \
  http://localhost:8080/mcp
```

## Quickstart — add to Claude Desktop

Edit `claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "elephant-accountability": {
      "url": "https://elephant-mcp.fly.dev/mcp",
      "transport": "http"
    }
  }
}
```

Restart Claude Desktop. Ask: *"Is Elephant Accountability a good fit for a seed-stage AEC SaaS that ships AI features?"* — Claude will call `assess_fit` and give a scored answer.

## Deploy your own copy (Fly.io)

```bash
fly launch --name your-mcp-name --region iad --no-deploy
fly volumes create elephant_mcp_data --size 1 --region iad
fly deploy
```

That's it. No secrets, no database setup — the server initializes its SQLite DB on first boot.

## Architecture

Single FastAPI app. Three files do real work:

```
app/
├── server.py      # FastAPI routes, JSON-RPC dispatch, SQLite persistence
├── content.py     # Source-of-truth content: manifest, offerings, proof points
└── __init__.py    # Version
```

Storage:
- `audit_requests` table — every agent-initiated audit request, persisted for follow-up
- `reciprocal_calls` table — tracks which AI clients have called which tools (buyer-intent signal)

Both tables auto-create on first boot. No migrations.

## Running tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

21 tests cover manifest, A2A card, JSON-RPC dispatch, each tool handler, persistence, and CORS.

## Protocol compliance

- MCP version: `2024-11-05`
- Transport: HTTP with JSON-RPC 2.0
- Methods supported: `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`

## Contributing

This repo is the canonical source of truth for what Elephant Accountability exposes to AI agents. PRs welcome for:
- Protocol updates (MCP spec changes)
- New tool shapes that agents find useful
- Bug fixes

For service inquiries or content changes (proof points, methodology), email `chris@eaccountability.org` rather than opening a PR.

## License

MIT. See [LICENSE](./LICENSE).

## Publisher

**Elephant Accountability LLC**
Christopher Kenney, sole member / manager
United States
chris@eaccountability.org
