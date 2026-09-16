"""
Configuration centrale â chargÃ©e depuis .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ââ Telegram ââââââââââââââââââââââââââââââââââââââ
    API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    SESSION_NAME: str = os.getenv("TELEGRAM_SESSION", "bv_copier_session")
    PHONE: str = os.getenv("TELEGRAM_PHONE", "")

    # ââ Canaux ââââââââââââââââââââââââââââââââââââââââ
    SOURCE_CHANNEL: str = os.getenv("SOURCE_CHANNEL", "")
    TARGET_CHANNEL: str = os.getenv("TARGET_CHANNEL", "")

    # ââ Comportement ââââââââââââââââââââââââââââââââââ
    ORDER_ADMIN: str = os.getenv("ORDER_ADMIN", "bvOrderAdmin")
    TEST_MODE: bool = os.getenv("TEST_MODE", "false").lower() == "true"
    PUBLISH_DELAY: float = float(os.getenv("PUBLISH_DELAY", "1.5"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    ALBUM_COLLECT_TIMEOUT: float = float(os.getenv("ALBUM_COLLECT_TIMEOUT", "3"))

    # ââ Traduction ââââââââââââââââââââââââââââââââââââ
    SOURCE_LANG: str = os.getenv("SOURCE_LANG", "ru")
    TARGET_LANG: str = os.getenv("TARGET_LANG", "ar")

    # ââ Web âââââââââââââââââââââââââââââââââââââââââââ
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int = int(os.getenv("WEB_PORT", "8000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "changeme")

    # ââ Base de donnÃ©es âââââââââââââââââââââââââââââââ
    DB_PATH: str = os.getenv("DB_PATH", "data/copier.db")

    @classmethod
    def validate(cls) -> list[str]:
        """Retourne une liste d'erreurs de configuration."""
        errors = []
        if not cls.API_ID:
            errors.append("TELEGRAM_API_ID manquant ou invalide (doit Ãªtre un entier).")
        if not cls.API_HASH:
            errors.append("TELEGRAM_API_HASH manquant.")
        if not cls.SOURCE_CHANNEL:
            errors.append("SOURCE_CHANNEL manquant.")
        if not cls.TARGET_CHANNEL:
            errors.append("TARGET_CHANNEL manquant.")
        return errors

    @classmethod
    def ensure_dirs(cls) -> None:
        """CrÃ©e les dossiers nÃ©cessaires si absents."""
        Path(cls.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(exist_ok=True)

    @classmethod
    def summary(cls) -> dict:
        return {
            "source_channel": cls.SOURCE_CHANNEL,
            "target_channel": cls.TARGET_CHANNEL,
            "order_admin": cls.ORDER_ADMIN,
            "test_mode": cls.TEST_MODE,
            "publish_delay": cls.PUBLISH_DELAY,
            "source_lang": cls.SOURCE_LANG,
            "target_lang": cls.TARGET_LANG,
        }
