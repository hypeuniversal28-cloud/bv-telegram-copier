"""
Publication vers le canal Telegram cible.
Gère : texte seul, photo seule, photo+caption, album, vidéo.
"""
import asyncio
from telethon import TelegramClient
from telethon.tl.types import InputFile
from config import Config
from modules.logger import log
from modules.downloader import MediaFile


class Publisher:
    def __init__(self, client: TelegramClient, target_channel: str):
        self.client = client
        self.target_channel = target_channel

    async def _get_target(self):
        """Résout l'entité du canal cible (avec cache Telethon)."""
        return await self.client.get_entity(self.target_channel)

    async def publish_text(self, text: str) -> int | None:
        """Publie un message texte pur."""
        if Config.TEST_MODE:
            log.info(f"[TEST] Texte → (non publié)\n{text}")
            return None
        try:
            target = await self._get_target()
            msg = await self.client.send_message(target, text)
            log.info(f"[PUBLISH] Texte publié → msg#{msg.id}")
            return msg.id
        except Exception as e:
            log.error(f"[ERROR] Publication texte : {e}")
            raise

    async def publish_photo(self, media_file: MediaFile, caption: str = "") -> int | None:
        """Publie une seule photo avec caption."""
        if Config.TEST_MODE:
            log.info(f"[TEST] Photo → {media_file.path} (non publiée)\nCaption: {caption}")
            return None
        try:
            target = await self._get_target()
            msg = await self.client.send_file(
                target,
                file=media_file.path,
                caption=caption or None,
                force_document=False,
            )
            log.info(f"[PUBLISH] Photo publiée → msg#{msg.id}")
            return msg.id
        except Exception as e:
            log.error(f"[ERROR] Publication photo : {e}")
            raise

    async def publish_album(
        self,
        media_files: list[MediaFile],
        caption: str = "",
    ) -> int | None:
        """
        Publie un album (groupe de médias).
        La caption est placée sur le premier media.
        """
        if not media_files:
            return None

        if Config.TEST_MODE:
            log.info(
                f"[TEST] Album → {len(media_files)} fichiers (non publié)\n"
                f"Caption: {caption}"
            )
            return None

        try:
            target = await self._get_target()
            files = [mf.path for mf in media_files]

            # Telethon : send_file avec liste = album
            msgs = await self.client.send_file(
                target,
                file=files,
                caption=caption or None,
            )

            # send_file retourne une liste si plusieurs fichiers
            first_id = msgs[0].id if isinstance(msgs, list) else msgs.id
            log.info(
                f"[PUBLISH] Album de {len(media_files)} médias publié → msg#{first_id}"
            )
            return first_id
        except Exception as e:
            log.error(f"[ERROR] Publication album : {e}")
            raise

    async def publish_video(self, media_file: MediaFile, caption: str = "") -> int | None:
        """Publie une vidéo avec caption."""
        if Config.TEST_MODE:
            log.info(f"[TEST] Vidéo → {media_file.path} (non publiée)\nCaption: {caption}")
            return None
        try:
            target = await self._get_target()
            msg = await self.client.send_file(
                target,
                file=media_file.path,
                caption=caption or None,
                supports_streaming=True,
            )
            log.info(f"[PUBLISH] Vidéo publiée → msg#{msg.id}")
            return msg.id
        except Exception as e:
            log.error(f"[ERROR] Publication vidéo : {e}")
            raise

    async def publish_with_retry(
        self,
        publish_fn,
        *args,
        max_retries: int = Config.MAX_RETRIES,
        **kwargs,
    ) -> int | None:
        """
        Enveloppe générique avec retry automatique.
        Gère le FloodWaitError de Telegram.
        """
        for attempt in range(1, max_retries + 1):
            try:
                result = await publish_fn(*args, **kwargs)
                return result
            except Exception as e:
                err_str = str(e).lower()

                # FloodWaitError : attendre le délai demandé
                if "flood" in err_str or "wait" in err_str:
                    import re
                    wait_match = re.search(r"(\d+)", str(e))
                    wait_sec = int(wait_match.group(1)) if wait_match else 30
                    log.warning(
                        f"[RETRY] FloodWait : {wait_sec}s. Tentative {attempt}/{max_retries}"
                    )
                    await asyncio.sleep(wait_sec + 2)
                else:
                    log.warning(
                        f"[RETRY] Erreur tentative {attempt}/{max_retries} : {e}"
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(5 * attempt)
                    else:
                        raise
        return None
