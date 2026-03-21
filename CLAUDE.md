# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Chop Airtime** is a Nigerian-focused AI chatbot that provides free airtime top-ups to Nigerian mobile numbers. Users interact via a web chat interface or WhatsApp. The agent autonomously disburses airtime (funded by an owner-preloaded wallet) at no cost to the user.

- Business rules: ₦5,000 initial wallet, ₦500 lifetime cap per user, ₦50 min / ₦500 max per top-up
- Supported networks: MTN, Airtel, Glo, 9mobile (Nigerian numbers only, 11 digits)
- Full specs are in `ChopAirtime_PRD_v1.docx` (product) and `ChopAirtime_TRD_v1.docx` (technical)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.11+) |
| Agent Orchestration | LangGraph (StateBased graph with tool-calling) |
| LLM | GPT-4o (OpenAI); Claude Sonnet 4.6 as fallback |
| Frontend | Next.js or plain HTML/Tailwind (mobile-responsive) |
| Database | Supabase (PostgreSQL) |
| WhatsApp Channel | Evolution API (webhook-based) |
| VTU Provider | VTpass (primary) / VTU.ng (fallback) |
| Backend Hosting | Railway or Render |
| Frontend Hosting | Vercel |
| Notifications | SMTP or Slack webhook (low-balance alerts) |

---

## Architecture

```
[Web Chat UI]      ──────────────────────────────────────────┐
                                                              ↓
[WhatsApp User] → [Evolution API Webhook] → [FastAPI Backend] → [LangGraph Agent] → [VTU API]
                                                              ↓
                                                         [Supabase]
                                                              ↓
                                                        [Notifier]
```

### API Endpoints (FastAPI)
- `POST /chat` — Web chat messages
- `POST /webhook/whatsapp` — Evolution API webhook (must validate HMAC signature)
- `GET /health` — Health check

### LangGraph Agent Flow
Graph nodes execute in sequence: `greet → collect_slots → validate → confirm → execute → respond`

1. **greet** — introduces the bot
2. **collect_slots** — conversationally collects phone number + amount
3. **validate** — checks 11-digit format, network prefix detection (auto-detects MTN/Airtel/Glo/9mobile), user cap check against Supabase
4. **confirm** — repeats details back to user for confirmation
5. **execute** — calls VTU API with idempotency key, logs transaction to Supabase
6. **respond** — success/failure/cap-exceeded message in Nigerian English with Pidgin flavour

### Database Schema (Supabase PostgreSQL)
```sql
-- users: unique users and cumulative top-up totals
users(id, identifier, channel, total_received, created_at, updated_at)

-- transactions: every top-up attempt for audit
transactions(id, user_id, phone_number, network, amount, status, vtu_reference, vtu_response JSONB, created_at)

-- wallet_snapshots: periodic owner wallet balance snapshots
wallet_snapshots(id, balance, snapshot_at)
```

`identifier` is phone number for WhatsApp users, session ID for web users.

---

## Environment Variables

```
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
VTPASS_API_KEY=
VTPASS_SECRET_KEY=
VTU_NG_JWT_TOKEN=
EVOLUTION_API_WEBHOOK_SECRET=
SMTP_HOST=
SMTP_USER=
SMTP_PASS=
SLACK_WEBHOOK_URL=
LOW_BALANCE_THRESHOLD=500
```

---

## Key Implementation Constraints

- **Idempotency**: Use idempotency keys for all VTU API calls to prevent duplicate disbursements
- **Webhook security**: Always validate Evolution API HMAC signature before processing
- **Prompt injection**: System prompt must be hardened; agent should refuse off-topic requests
- **Fallback**: If VTpass fails, retry once then fall back to VTU.ng before returning an error
- **Low-balance alert**: Trigger notification when wallet drops below ₦500
- **Agent personality**: Nigerian English with Pidgin phrases ("No wahala", "Omo!", "Correct!", "I don send am")

---

## Development Phases (MVP: 7 days)

- **Phase 1 (Days 1–3):** FastAPI scaffolding, Supabase schema, LangGraph agent, VTU integration
- **Phase 2 (Days 4–5):** Web frontend, deploy to Vercel
- **Phase 3 (Days 6–7):** WhatsApp via Evolution API, session persistence
- **Phase 4:** Load testing (target: 50 concurrent users), monitoring
