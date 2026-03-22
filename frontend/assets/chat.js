/* Chop Airtime — web chat */

// ── API base URL ────────────────────────────────────────────────────────────
// Opened as file:// in dev  → talk to local backend on 8090
// Opened via http server    → same host:port (works for any port)
// Production (different origin not needed) → same origin
function getApiBase() {
  const { protocol, hostname, port } = window.location;
  if (protocol === "file:") return "http://localhost:8090";
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return `${protocol}//${hostname}:${port}`;
  }
  // Production: point to Railway backend
  return "chopairtime.railway.internal"; // ← replace with your Railway URL after deploy
}
const API_BASE = getApiBase();

// ── DOM refs ────────────────────────────────────────────────────────────────
const messagesEl  = document.getElementById("messages");
const inputEl     = document.getElementById("input");
const sendBtn     = document.getElementById("send-btn");
const typingRow   = document.getElementById("typing-row");
const chipsEl     = document.getElementById("chips");

// ── Session ID (persistent per browser tab) ─────────────────────────────────
const SESSION_ID = sessionStorage.getItem("chop_session") || crypto.randomUUID();
sessionStorage.setItem("chop_session", SESSION_ID);

// ── Helpers ─────────────────────────────────────────────────────────────────
function timestamp() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** Detect whether the bot message is a success/failure response */
function bubbleModifier(text) {
  const t = text.toLowerCase();
  if (t.includes("i don send am") || t.includes("✅") || t.includes("airtime don land"))
    return "bubble-success";
  if (t.includes("something no go well") || t.includes("sorry") || t.includes("😔"))
    return "bubble-failure";
  return "";
}

/** Detect whether quick-reply chips should appear after this bot message */
function shouldShowChips(text) {
  const t = text.toLowerCase();
  return (
    t.includes("confirm") ||
    t.includes("correct?") ||
    t.includes("proceed") ||
    t.includes("yes") && (t.includes("send") || t.includes("top up"))
  );
}

// ── Render a message bubble ──────────────────────────────────────────────────
function appendBubble(text, role) {
  hideChips();
  const isBot = role !== "user";

  const row = document.createElement("div");
  row.className = `flex items-end gap-2 bubble-in ${isBot ? "" : "flex-row-reverse"}`;

  // Avatar — bot only
  if (isBot) {
    const av = document.createElement("div");
    av.className = "w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-white text-xs font-bold self-end";
    av.style.background = "linear-gradient(135deg,#2db865,#008751)";
    av.textContent = "CA";
    row.appendChild(av);
  }

  // Bubble wrapper (for bubble + timestamp stacked)
  const col = document.createElement("div");
  col.className = `flex flex-col gap-1 max-w-[78%] ${isBot ? "items-start" : "items-end"}`;

  const bubble = document.createElement("div");
  const modifier = isBot ? bubbleModifier(text) : "";

  bubble.className = [
    "px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words",
    isBot
      ? `bg-white border border-gray-100 shadow-sm rounded-2xl rounded-bl-sm text-gray-800 ${modifier}`
      : "text-white rounded-2xl rounded-br-sm",
  ].join(" ");

  if (!isBot) bubble.style.background = "linear-gradient(135deg,#2db865,#008751)";

  bubble.textContent = text;

  const ts = document.createElement("span");
  ts.className = "text-[10px] text-gray-400 px-1";
  ts.textContent = timestamp();

  col.appendChild(bubble);
  col.appendChild(ts);
  row.appendChild(col);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  // Show chips if this is a confirmation prompt
  if (isBot && shouldShowChips(text)) {
    showChips([
      { label: "✅ Yes, send it",   cls: "chip-confirm", value: "Yes, please send it" },
      { label: "✏️ Change details", cls: "chip-change",  value: "No, I want to change the details" },
    ]);
  }
}

// ── Quick-reply chips ────────────────────────────────────────────────────────
function showChips(options) {
  chipsEl.innerHTML = "";
  options.forEach(({ label, cls, value }) => {
    const btn = document.createElement("button");
    btn.className = `chip ${cls}`;
    btn.textContent = label;
    btn.addEventListener("click", () => {
      hideChips();
      sendMessage(value);
    });
    chipsEl.appendChild(btn);
  });
  chipsEl.classList.add("visible");
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideChips() {
  chipsEl.classList.remove("visible");
  chipsEl.innerHTML = "";
}

// ── Loading state ────────────────────────────────────────────────────────────
function setLoading(loading) {
  sendBtn.disabled = loading;
  inputEl.disabled = loading;
  sendBtn.style.opacity = loading ? "0.6" : "1";
  typingRow.style.display = loading ? "block" : "none";
  if (loading) messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ── Send a message ────────────────────────────────────────────────────────────
async function sendMessage(text) {
  const trimmed = text.trim();
  if (!trimmed) return;

  appendBubble(trimmed, "user");
  inputEl.value = "";
  setLoading(true);

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID, message: trimmed }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    appendBubble(data.reply, "bot");
  } catch (err) {
    appendBubble("Hmm, something no go well o. Abeg try again! 😔", "bot");
    console.error(err);
  } finally {
    setLoading(false);
    inputEl.focus();
  }
}

// ── Start session (greeting) ──────────────────────────────────────────────────
async function startSession() {
  setLoading(true);
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID, message: "" }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    appendBubble(data.reply, "bot");
  } catch {
    appendBubble("Welcome to Chop Airtime! 🎉\nAbeg, which number you wan top up?", "bot");
  } finally {
    setLoading(false);
    inputEl.focus();
  }
}

// ── Event listeners ───────────────────────────────────────────────────────────
sendBtn.addEventListener("click", () => sendMessage(inputEl.value));
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(inputEl.value);
  }
});

// ── Boot ──────────────────────────────────────────────────────────────────────
startSession();
