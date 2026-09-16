"""
Serveur d'authentification Telegram — interface web.
Lance ce script, ouvre l'URL, entre le code SMS reçu sur Telegram.
Une fois authentifié, le bot démarre automatiquement.
"""
import asyncio
import os
import sys
import subprocess
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from config import Config
from modules.logger import log

app = FastAPI()

# ── État global ───────────────────────────────────────────────────────────
_state = {
    "step": "idle",        # idle | code_sent | need_password | done | error
    "phone_hash": None,
    "client": None,
    "error": None,
    "account_name": None,
}


HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BV Telegram Copier — Connexion</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .card {
    background: #13131a;
    border: 1px solid #2a2a3a;
    border-radius: 16px;
    padding: 40px;
    width: 100%;
    max-width: 420px;
    text-align: center;
  }
  .logo { font-size: 48px; margin-bottom: 16px; }
  h1 { font-size: 22px; font-weight: 700; margin-bottom: 8px; color: #fff; }
  .subtitle { font-size: 14px; color: #888; margin-bottom: 32px; }
  .step { display: none; }
  .step.active { display: block; }
  .info-box {
    background: #1a1a2e;
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 24px;
    font-size: 14px;
    color: #aaa;
    text-align: left;
  }
  .info-box strong { color: #7eb8f7; }
  input[type="text"] {
    width: 100%;
    background: #1e1e2e;
    border: 1px solid #3a3a5a;
    border-radius: 10px;
    color: #fff;
    font-size: 20px;
    letter-spacing: 6px;
    padding: 14px;
    text-align: center;
    margin-bottom: 20px;
    outline: none;
    transition: border-color 0.2s;
  }
  input[type="text"]:focus { border-color: #5b8ef0; }
  button {
    width: 100%;
    background: #5b8ef0;
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 14px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s, opacity 0.2s;
  }
  button:hover { background: #4a7de0; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .success-box {
    background: #0d2a1a;
    border: 1px solid #1a5a30;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 24px;
    color: #4caf88;
  }
  .success-box .icon { font-size: 40px; margin-bottom: 10px; }
  .error-box {
    background: #2a0d0d;
    border: 1px solid #5a1a1a;
    border-radius: 10px;
    padding: 14px;
    color: #f77;
    font-size: 13px;
    margin-bottom: 16px;
    display: none;
  }
  .spinner {
    display: inline-block;
    width: 20px; height: 20px;
    border: 2px solid rgba(255,255,255,0.2);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    margin-right: 8px;
    vertical-align: middle;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .redirect-msg { font-size: 13px; color: #888; margin-top: 12px; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">📡</div>
  <h1>BV Telegram Copier</h1>
  <p class="subtitle">Connexion au compte Telegram</p>

  <!-- Étape 1 : envoi du code -->
  <div class="step active" id="step-send">
    <div class="info-box">
      Le code de vérification sera envoyé sur Telegram au numéro<br>
      <strong id="phone-display">chargement…</strong>
    </div>
    <div class="error-box" id="err-send"></div>
    <button id="btn-send" onclick="sendCode()">Envoyer le code</button>
  </div>

  <!-- Étape 2 : saisie du code -->
  <div class="step" id="step-code">
    <div class="info-box">
      Entre le code reçu sur ton application <strong>Telegram</strong>
      (format : 5 chiffres)
    </div>
    <div class="error-box" id="err-code"></div>
    <input type="text" id="code-input" placeholder="12345" maxlength="10"
           inputmode="numeric" autocomplete="off">
    <button id="btn-verify" onclick="verifyCode()">Confirmer</button>
  </div>

  <!-- Étape 3 : mot de passe 2FA -->
  <div class="step" id="step-pwd">
    <div class="info-box">
      Ton compte a la <strong>vérification en 2 étapes</strong> activée.<br>
      Entre ton mot de passe Telegram.
    </div>
    <div class="error-box" id="err-pwd"></div>
    <input type="text" id="pwd-input" placeholder="Mot de passe" maxlength="60"
           style="letter-spacing:1px">
    <button id="btn-pwd" onclick="sendPassword()">Confirmer</button>
  </div>

  <!-- Étape finale : succès -->
  <div class="step" id="step-done">
    <div class="success-box">
      <div class="icon">✅</div>
      <strong>Connecté en tant que <span id="account-name"></span></strong>
    </div>
    <p class="redirect-msg">✅ Bot actif — copie en cours…</p>
  </div>

  <!-- Étape erreur critique -->
  <div class="step" id="step-error">
    <div class="error-box" style="display:block" id="err-fatal"></div>
    <button onclick="location.reload()">Réessayer</button>
  </div>
</div>

<script>
let phone = '';

async function init() {
  const r = await fetch('/auth/status');
  const d = await r.json();
  phone = d.phone;
  document.getElementById('phone-display').textContent = phone;
  if (d.step === 'done') showDone(d.account_name);
}

function showStep(id) {
  document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

async function sendCode() {
  const btn = document.getElementById('btn-send');
  btn.dataset.label = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Envoi du code…';
  const err = document.getElementById('err-send');
  err.style.display = 'none';

  const r = await fetch('/auth/send-code', { method: 'POST' });
  const d = await r.json();
  btn.disabled = false;
  btn.innerHTML = btn.dataset.label || 'Envoyer le code';

  if (d.ok) {
    showStep('step-code');
    setTimeout(() => document.getElementById('code-input').focus(), 100);
  } else {
    err.textContent = d.error || 'Erreur inconnue';
    err.style.display = 'block';
  }
}

async function verifyCode() {
  const code = document.getElementById('code-input').value.trim();
  if (!code) return;
  const btn = document.getElementById('btn-verify');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Vérification…';
  const err = document.getElementById('err-code');
  err.style.display = 'none';

  const r = await fetch('/auth/verify-code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code })
  });
  const d = await r.json();
  btn.disabled = false;
  btn.innerHTML = 'Confirmer';

  if (d.ok) {
    showDone(d.account_name);
  } else if (d.need_password) {
    showStep('step-pwd');
    setTimeout(() => document.getElementById('pwd-input').focus(), 100);
  } else {
    err.textContent = d.error || 'Code incorrect';
    err.style.display = 'block';
  }
}

async function sendPassword() {
  const pwd = document.getElementById('pwd-input').value;
  if (!pwd) return;
  const btn = document.getElementById('btn-pwd');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Vérification…';
  const err = document.getElementById('err-pwd');
  err.style.display = 'none';

  const r = await fetch('/auth/verify-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pwd })
  });
  const d = await r.json();
  btn.disabled = false;
  btn.innerHTML = 'Confirmer';

  if (d.ok) {
    showDone(d.account_name);
  } else {
    err.textContent = d.error || 'Mot de passe incorrect';
    err.style.display = 'block';
  }
}

function showDone(name) {
  document.getElementById('account-name').textContent = name || '';
  showStep('step-done');
  // Lancer le bot côté serveur (une seule fois)
  if (!window._botStarted) {
    window._botStarted = true;
    fetch('/auth/start-bot', { method: 'POST' });
  }
}

// Écouter Enter sur les inputs
document.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const step = document.querySelector('.step.active');
  if (!step) return;
  if (step.id === 'step-code') verifyCode();
  if (step.id === 'step-pwd') sendPassword();
});

init();
</script>
</body>
</html>
"""


# ── Routes d'auth ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_redirect():
    return """<html><body><script>window.location.href='/';</script></body></html>"""


@app.get("/auth/status")
async def auth_status():
    return {
        "step": _state["step"],
        "phone": Config.PHONE,
        "account_name": _state.get("account_name"),
    }


@app.post("/auth/send-code")
async def auth_send_code():
    try:
        client = TelegramClient(Config.SESSION_NAME, Config.API_ID, Config.API_HASH)
        await client.connect()

        if await client.is_user_authorized():
            me = await client.get_me()
            _state["step"] = "done"
            _state["account_name"] = me.first_name
            _state["client"] = client
            # Auto-start bot if already authorized
            if not _state.get("bot_started"):
                _state["bot_started"] = True
                _do_start_bot()
            return {"ok": True, "already_auth": True, "account_name": me.first_name}

        result = await client.send_code_request(Config.PHONE)
        _state["phone_hash"] = result.phone_code_hash
        _state["client"] = client
        _state["step"] = "code_sent"
        log.info(f"[AUTH] Code envoyé au {Config.PHONE}")
        return {"ok": True}

    except Exception as e:
        _state["step"] = "error"
        _state["error"] = str(e)
        log.error(f"[AUTH] Erreur envoi code : {e}")
        return {"ok": False, "error": str(e)}


@app.post("/auth/verify-code")
async def auth_verify_code(body: dict):
    code = body.get("code", "").strip()
    client: TelegramClient = _state.get("client")
    if not client or not _state.get("phone_hash"):
        return {"ok": False, "error": "Session expirée, rafraîchissez la page"}

    try:
        await client.sign_in(
            phone=Config.PHONE,
            code=code,
            phone_code_hash=_state["phone_hash"],
        )
        me = await client.get_me()
        _state["step"] = "done"
        _state["account_name"] = me.first_name
        log.info(f"[AUTH] ✅ Authentifié : {me.first_name}")
        return {"ok": True, "account_name": me.first_name}

    except SessionPasswordNeededError:
        _state["step"] = "need_password"
        return {"ok": False, "need_password": True}
    except Exception as e:
        log.error(f"[AUTH] Erreur vérification code : {e}")
        return {"ok": False, "error": str(e)}


@app.post("/auth/verify-password")
async def auth_verify_password(body: dict):
    password = body.get("password", "")
    client: TelegramClient = _state.get("client")
    if not client:
        return {"ok": False, "error": "Session expirée"}

    try:
        await client.sign_in(password=password)
        me = await client.get_me()
        _state["step"] = "done"
        _state["account_name"] = me.first_name
        log.info(f"[AUTH] ✅ Authentifié (2FA) : {me.first_name}")
        return {"ok": True, "account_name": me.first_name}

    except Exception as e:
        log.error(f"[AUTH] Erreur 2FA : {e}")
        return {"ok": False, "error": str(e)}


def _do_start_bot():
    """Lance main.py en arrière-plan (mode NO_WEB_SERVER=1)."""
    client: TelegramClient = _state.get("client")
    if client:
        # Déconnecter le client auth en thread séparé (non-async)
        import asyncio as _aio
        try:
            loop = _aio.get_event_loop()
            if loop.is_running():
                loop.create_task(client.disconnect())
        except Exception:
            pass
        _state["client"] = None

    def _launch():
        import time
        time.sleep(2)
        # Créer le dossier logs si absent
        Path("logs").mkdir(exist_ok=True)
        env = dict(os.environ)
        env["NO_WEB_SERVER"] = "1"   # main.py ne démarre pas uvicorn
        proc = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=str(Path(__file__).parent),
            env=env,
            # Logs visibles dans Railway (héritage stdout/stderr)
        )
        log.info(f"[AUTH] main.py démarré (PID {proc.pid})")

    threading.Thread(target=_launch, daemon=True).start()
    log.info("[AUTH] Bot lancé en arrière-plan")


@app.post("/auth/start-bot")
async def auth_start_bot():
    """Déconnecte le client auth, puis lance main.py en arrière-plan."""
    if _state.get("bot_started"):
        return {"ok": True, "already_started": True}
    _state["bot_started"] = True
    _do_start_bot()
    return {"ok": True}


# ── Health check pour le tunnel ───────────────────────────────────────────

@app.get("/api/state")
async def api_state():
    return {"running": _state["step"] == "done", "auth_step": _state["step"]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
