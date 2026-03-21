# Chop Airtime 🇳🇬

A Nigerian AI chatbot that sends **free airtime** to any Nigerian mobile number. Users chat with the bot (web or WhatsApp), provide a phone number and amount, and the bot disburses airtime instantly — funded by the owner's pre-loaded wallet.

---

## How It Works

```
User (Web or WhatsApp)
        ↓
   FastAPI Backend
        ↓
  LangGraph AI Agent  ←→  PostgreSQL (Neon)
        ↓
  VTpass API  →  (fallback) VTU.ng API
```

The AI agent guides the user through a 6-step flow:

```
Greet → Collect phone & amount → Validate → Confirm → Disburse → Respond
```

Only 2 of the 6 steps use an LLM. The rest are deterministic rules — keeping it fast, cheap, and predictable.

---

## Business Rules

| Rule | Value |
|------|-------|
| Lifetime cap per user | ₦500 |
| Minimum top-up | ₦50 |
| Maximum top-up | ₦500 |
| Supported networks | MTN, Airtel, Glo, 9mobile |
| Supported number format | 11-digit Nigerian numbers (e.g. 08031234567) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.12 |
| AI Agent | LangGraph |
| LLM | GPT-4o (primary) → Mistral → Claude Sonnet (fallbacks) |
| Database | Neon (PostgreSQL) |
| Airtime API | VTpass (primary) → VTU.ng (fallback) |
| WhatsApp | Evolution API |
| Frontend | Plain HTML + Tailwind CSS |

---

## Project Structure

```
chop_airtime/
├── backend/
│   ├── main.py               # FastAPI app entry point
│   ├── config.py             # All environment variables
│   ├── database.py           # All database operations
│   ├── models.py             # Request/response models
│   ├── agent/
│   │   ├── graph.py          # LangGraph wiring
│   │   ├── nodes.py          # The 6 agent steps
│   │   ├── state.py          # Shared state across steps
│   │   ├── tools.py          # LLM tool definitions
│   │   └── prompts.py        # All prompts and message templates
│   ├── routes/
│   │   ├── chat.py           # POST /chat  (web)
│   │   ├── webhook.py        # POST /webhook/whatsapp
│   │   └── health.py         # GET /health
│   ├── services/
│   │   ├── vtpass.py         # VTpass API client
│   │   ├── vtu_ng.py         # VTU.ng fallback client
│   │   ├── vtu_dispatcher.py # Tries VTpass twice, then VTU.ng
│   │   ├── evolution.py      # Send WhatsApp messages
│   │   └── notifier.py       # Low-balance Slack/email alerts
│   ├── utils/
│   │   ├── network_detect.py # Phone prefix → MTN/Airtel/Glo/9mobile
│   │   └── idempotency.py    # Prevents duplicate disbursements
│   └── requirements.txt
├── frontend/
│   ├── index.html            # Chat UI
│   └── assets/chat.js        # Handles messages and API calls
├── supabase/
│   └── schema.sql            # Database schema (run once)
├── .env.example              # All environment variables documented
└── Procfile                  # For Railway/Render deployment
```

---

## Prerequisites

- Python 3.12
- A [Neon](https://neon.tech) account (free) — for the database
- A [VTpass](https://vtpass.com) account — for airtime disbursement
- At least one LLM API key: [OpenAI](https://platform.openai.com), [Mistral](https://console.mistral.ai), or [Anthropic](https://console.anthropic.com)

---

## Local Setup

### 1. Clone and create a virtual environment

```bash
cd chop_airtime
py -3.12 -m venv backend/.venv
source backend/.venv/Scripts/activate   # Windows Git Bash
# or on Mac/Linux:
# source backend/.venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Set up the database

1. Go to [console.neon.tech](https://console.neon.tech) → create a project
2. Open the **SQL Editor** and paste the contents of `supabase/schema.sql`, then run it
3. Copy your **Connection string** — it looks like:
   ```
   postgresql://user:password@ep-xxx.neon.tech/neondb?sslmode=require
   ```

### 4. Configure environment variables

```bash
cp .env.example backend/.env
```

Open `backend/.env` and fill in the required values:

```bash
# Required — app won't start without these
DATABASE_URL=postgresql://...          # from Neon
OPENAI_API_KEY=sk-...                  # or MISTRAL_API_KEY / ANTHROPIC_API_KEY

# Required for airtime disbursement
VTPASS_API_KEY=your-api-key
VTPASS_SECRET_KEY=SK_...
VTPASS_BASE_URL=https://sandbox.vtpass.com/api   # use sandbox for testing
```

Everything else (WhatsApp, email alerts, Slack) is optional and can be added later.

### 5. Run the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 6. Open the frontend

Open `frontend/index.html` directly in your browser, or serve it:

```bash
cd frontend
python -m http.server 3000
# then open http://localhost:3000
```

---

## Testing the Flow

### Quick health check
```bash
curl http://localhost:8000/health
# → {"status": "ok", "version": "1.0.0"}
```

### Start a chat session
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-1", "message": ""}' | python -m json.tool
```

This returns the greeting message. Then send follow-up messages using the same `session_id`:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-1", "message": "08031234567"}' | python -m json.tool
```

### Using the sandbox (recommended before going live)

Set `VTPASS_BASE_URL=https://sandbox.vtpass.com/api` in your `.env` and use sandbox credentials from [sandbox.vtpass.com/account](https://sandbox.vtpass.com/account). The sandbox processes fake transactions with real response structures — perfect for testing without spending money.

---

## Switching LLM Providers

The app supports three LLM providers. Set `LLM_PROVIDER` in your `.env`:

```bash
LLM_PROVIDER=openai      # GPT-4o (default)
LLM_PROVIDER=mistral     # Mistral Large
LLM_PROVIDER=anthropic   # Claude Sonnet 4.6
```

If the primary provider fails, the app automatically falls back to the others. You only need API keys for the providers you want to use.

---

## API Reference

### `GET /health`
Returns server status.
```json
{"status": "ok", "version": "1.0.0"}
```

### `POST /chat`
Send a message in the web chat.

**Request:**
```json
{
  "session_id": "any-unique-string",
  "message": "08031234567"
}
```
Send `message: ""` on the first call to trigger the greeting.

**Response:**
```json
{
  "session_id": "any-unique-string",
  "reply": "Correct! ✅ I don send am!..."
}
```

### `POST /webhook/whatsapp`
Receives Evolution API webhook events. Validates HMAC-SHA256 signature before processing.

---

## Deployment

### Backend → Railway

1. Push code to GitHub
2. Create a new Railway project → **Deploy from GitHub repo**
3. Set the root directory to `backend/`
4. Add all environment variables from `.env`
5. Railway uses the `Procfile` automatically:
   ```
   web: uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

### Frontend → Vercel

1. Connect your GitHub repo to [Vercel](https://vercel.com)
2. Set the root directory to `frontend/`
3. No build command needed — it's plain HTML
4. Update `API_BASE` in `frontend/assets/chat.js` to your Railway backend URL

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Neon PostgreSQL connection string |
| `LLM_PROVIDER` | No | `openai` / `mistral` / `anthropic` (default: `openai`) |
| `OPENAI_API_KEY` | If using OpenAI | GPT-4o API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Claude API key |
| `MISTRAL_API_KEY` | If using Mistral | Mistral API key |
| `MISTRAL_MODEL` | No | Model name (default: `mistral-large-latest`) |
| `VTPASS_API_KEY` | Yes | VTpass API key |
| `VTPASS_SECRET_KEY` | Yes | VTpass secret key (format: `SK_...`) |
| `VTPASS_BASE_URL` | No | Default: `https://vtpass.com/api` |
| `VTU_NG_JWT_TOKEN` | No | VTU.ng fallback token |
| `EVOLUTION_API_URL` | For WhatsApp | Evolution API server URL |
| `EVOLUTION_API_INSTANCE` | For WhatsApp | Instance name |
| `EVOLUTION_API_KEY` | For WhatsApp | Evolution API key |
| `EVOLUTION_API_WEBHOOK_SECRET` | For WhatsApp | HMAC signing secret |
| `SMTP_HOST` | For email alerts | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | No | Default: `587` |
| `SMTP_USER` | For email alerts | Sender email |
| `SMTP_PASS` | For email alerts | App password |
| `ALERT_EMAIL_TO` | For email alerts | Recipient email |
| `SLACK_WEBHOOK_URL` | For Slack alerts | Incoming webhook URL |
| `LOW_BALANCE_THRESHOLD` | No | Alert when wallet drops below this (default: `500`) |
| `USER_LIFETIME_CAP` | No | Max lifetime airtime per user in ₦ (default: `500`) |
| `MIN_TOPUP` | No | Minimum top-up amount in ₦ (default: `50`) |
| `MAX_TOPUP` | No | Maximum top-up amount in ₦ (default: `500`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `*`) |

---

## Common Issues

**`Cannot connect to database`**
- Check your `DATABASE_URL` is correct and includes `?sslmode=require`
- Neon pauses inactive projects — open the Neon console to wake it up

**`ResolutionImpossible` during pip install**
- Make sure you're using Python 3.12: `py -3.12 -m venv .venv`
- Try `pip install --upgrade pip` first

**VTpass returns non-success**
- Double-check you're using sandbox keys with the sandbox URL and vice versa
- Confirm `VTPASS_SECRET_KEY` starts with `SK_`

**LLM not responding**
- Verify the API key for your chosen `LLM_PROVIDER` is set and valid
- The app will log which provider it falls back to — check the terminal output
