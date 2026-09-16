"""
Téléchargement de médias depuis Telegram.
Gère photos, albums, vidéos, documents.
"""
import asyncio
import os
import tempfile
from pathlib import Path
from telethon.tl.types import (
    Message,
    MessageMediaPhoto,
    MessageMediaDocument,
)
from modules.logger import log


class MediaFile:
    """Représente un fichier média téléchargé."""
    def __init__(self, path, media_type, original_message_id):
        self.path = path; self.media_type = media_type; self.original_message_id = original_message_id
    def cleanup(self):
        try:
            if os.path.exists(self.path): os.remove(self.path)
        except Exception: pass


class Downloader:
    def __init__(self, client):
        self.client = client
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="tg_copier_"))

    def _tmp_path(self, message_id, suffix):
        return str(self._tmp_dir / f"msg_{message_id}{suffix}")

    def _detect_type(self, message):
        if isinstance(message.media, MessageMediaPhoto): return "photo"
        if isinstance(message.media, MessageMediaDocument):
            for attr in message.media.document.attributes:
                if "Video" in type(attr).__name__: return "video"
                if "Audio" in type(attr).__name__: return "audio"
            return "document"
        return "unknown"

    async def download_media(self, message):
        if not message.media: return None
        media_type = self._detect_type(message)
        suffix = {"photo": ".jpg", "video": ".mp4", "audio": ".mp3"}.get(media_type, ".bin")
        path = self._tmp_path(message.id, suffix)
        try:
            downloaded = await self.client.download_media(message.media, file=path)
            return MediaFile(str(downloaded), media_type, message.id) if downloaded else None
        except Exception as e:
            log.error(f"[ERROR] Download msg#{message.id}: {e}"); return None

    async def download_album(self, messages):
        media_files = []
        for msg in sorted(messages, key=lambda m: m.id):
            if msg.media:
                mf = await self.download_media(msg)
                if mf: media_files.append(mf)
                await asyncio.sleep(0.3)
        return media_files

    def cleanup(self):
        try:
            import shutil; shutil.rmtree(self._tmp_dir, ignore_errors=True)
        except Exception: pass
