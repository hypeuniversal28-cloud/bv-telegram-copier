"""
Point d'entrée principal — BV Telegram Copier.
Lance simultanément le listener Telegram et le dashboard web.
"""
import asyncio
import os
import sys
import signal
import uvicorn
from telethon import TelegramClient

from config import Config
from modules.logger import log
from modules.database import Database
from modules.listener import ChannelListener
from web.app import app as web_app, set_running


def banner() -> None:
    print("""
╔══════════════════════════════════════════════╗
║          BV TELEGRAM COPIER  v1.0            ║
║      Copie automatique canal → canal         ║
╚══════════════════════════════════════════════╝
""")


async def run_web(config: uvicorn.Config) -> None:
    """Lance le serveur FastAPI."""
    server = uvicorn.Server(config)
    await server.serve()


async def run_listener(client: TelegramClient) -> None:
    """Lance le listener Telegram."""
    listener = ChannelListener(
        client=client,
        source_channel=Config.SOURCE_CHANNEL,
        target_channel=Config.TARGET_CHANNEL,
    )
    await listener.start()


async def main() -> None:
    banner()

    # ── Validation de la config ──────────────────────────────────────────
    Config.ensure_dirs()
    errors = Config.validate()
    if errors:
        log.error("[ERROR] Erreurs de configuration :")
        for e in errors:
            log.error(f"  • {e}")
        log.error("  → Copiez .env.example vers .env et remplissez les valeurs.")
        sys.exit(1)

    log.info(f"  Source  : {Config.SOURCE_CHANNEL}")
    log.info(f"  Cible   : {Config.TARGET_CHANNEL}")
    log.info(f"  Admin   : {Config.ORDER_ADMIN}")
    log.info(f"  Mode    : {'🧪 TEST (pas de publication)' if Config.TEST_MODE else '🚀 PRODUCTION'}")

    # ── Base de données ──────────────────────────────────────────────────
    db = await Database.get()

    # Charger la config dynamique depuis la DB (si modifiée via le dashboard)
    saved_admin = await db.get_config("order_admin")
    if saved_admin:
        Config.ORDER_ADMIN = saved_admin

    saved_test = await db.get_config("test_mode")
    if saved_test:
        Config.TEST_MODE = saved_test == "true"

    # ── Client Telegram ──────────────────────────────────────────────────
    client = TelegramClient(
        Config.SESSION_NAME,
        Config.API_ID,
        Config.API_HASH,
    )

    await client.start()
    me = await client.get_me()
    log.info(f"  Compte  : {me.first_name} (@{me.username or me.id})")

    set_running(True)

    # ── Uvicorn config ───────────────────────────────────────────────────
    uvi_config = uvicorn.Config(
        app=web_app,
        host=Config.WEB_HOST,
        port=Config.WEB_PORT,
        log_level="warning",  # On gère nos propres logs
    )

    log.info(f"\n  Dashboard : http://localhost:{Config.WEB_PORT}\n")

    # ── Lancement: bot seul ou bot + web selon NO_WEB_SERVER ────────────
    no_web = os.getenv("NO_WEB_SERVER") == "1"
    try:
        if no_web:
            log.info("  Mode : bot uniquement (NO_WEB_SERVER=1)")
            await run_listener(client)
        else:
            await asyncio.gather(
                run_listener(client),
                run_web(uvi_config),
            )
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("\n[NEW POST] Arrêt demandé…")
    finally:
        set_running(False)
        await client.disconnect()
        await db.close()
        log.info("[NEW POST] Arrêt propre. À bientôt.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
