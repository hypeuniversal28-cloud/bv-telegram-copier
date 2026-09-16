"""
Point d'entrÃ©e principal â BV Telegram Copier.
Lance simultanÃ©ment le listener Telegram et le dashboard web.
"""
import asyncio
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
ââââââââââââââââââââââââââââââââââââââââââââââââ
â          BV TELEGRAM COPIER  v1.0            â
â      Copie automatique canal â canal         â
ââââââââââââââââââââââââââââââââââââââââââââââââ
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

    # ââ Validation de la config ââââââââââââââââââââââââââââââââââââââââââ
    Config.ensure_dirs()
    errors = Config.validate()
    if errors:
        log.error("[ERROR] Erreurs de configuration :")
        for e in errors:
            log.error(f"  â¢ {e}")
        log.error("  â Copiez .env.example vers .env et remplissez les valeurs.")
        sys.exit(1)

    log.info(f"  Source  : {Config.SOURCE_CHANNEL}")
    log.info(f"  Cible   : {Config.TARGET_CHANNEL}")
    log.info(f"  Admin   : {Config.ORDER_ADMIN}")
    log.info(f"  Mode    : {'ð§ª TEST (pas de publication)' if Config.TEST_MODE else 'ð PRODUCTION'}")

    # ââ Base de donnÃ©es ââââââââââââââââââââââââââââââââââââââââââââââââââ
    db = await Database.get()

    # Charger la config dynamique depuis la DB (si modifiÃ©e via le dashboard)
    saved_admin = await db.get_config("order_admin")
    if saved_admin:
        Config.ORDER_ADMIN = saved_admin

    saved_test = await db.get_config("test_mode")
    if saved_test:
        Config.TEST_MODE = saved_test == "true"

    # ââ Client Telegram ââââââââââââââââââââââââââââââââââââââââââââââââââ
    client = TelegramClient(
        Config.SESSION_NAME,
        Config.API_ID,
        Config.API_HASH,
    )

    await client.start()
    me = await client.get_me()
    log.info(f"  Compte  : {me.first_name} (@{me.username or me.id})")

    set_running(True)

    # ââ Uvicorn config âââââââââââââââââââââââââââââââââââââââââââââââââââ
    uvi_config = uvicorn.Config(
        app=web_app,
        host=Config.WEB_HOST,
        port=Config.WEB_PORT,
        log_level="warning",  # On gÃ¨re nos propres logs
    )

    log.info(f"\n  Dashboard : http://localhost:{Config.WEB_PORT}\n")

    # ââ Lancement parallÃ¨le ââââââââââââââââââââââââââââââââââââââââââââââ
    try:
        await asyncio.gather(
            run_listener(client),
            run_web(uvi_config),
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("\n[NEW POST] ArrÃªt demandÃ©â¦")
    finally:
        set_running(False)
        await client.disconnect()
        await db.close()
        log.info("[NEW POST] ArrÃªt propre. Ã bientÃ´t.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
