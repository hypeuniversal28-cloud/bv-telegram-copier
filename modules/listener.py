"""
Écoute le canal source et orchestre le traitement des messages.
Gère la collecte d'albums (grouped_id) avec un buffer temporisé.
"""
import asyncio
from collections import defaultdict
from telethon import TelegramClient, events
from telethon.tl.types import Message

from config import Config
from modules.logger import log
from modules.database import Database
from modules.downloader import Downloader, MediaFile
from modules.caption_processor import process_caption
from modules.publisher import Publisher


class AlbumBuffer:
    """
    Collecte les messages d'un même album (grouped_id) pendant TIMEOUT secondes,
    puis les transmet en groupe au handler.
    """

    def __init__(self, timeout: float, callback):
        self._buffers: dict[int, list[Message]] = defaultdict(list)
        self._timers: dict[int, asyncio.TimerHandle] = {}
        self._timeout = timeout
        self._callback = callback

    def add(self, message: Message) -> None:
        gid = message.grouped_id
        self._buffers[gid].append(message)
        if gid in self._timers: self._timers[gid].cancel()
        loop = asyncio.get_event_loop()
        self._timers[gid] = loop.call_later(self._timeout, lambda g=gid: asyncio.ensure_future(self._flush(g)))

    async def _flush(self, grouped_id):
        messages = self._buffers.pop(grouped_id, [])
        self._timers.pop(grouped_id, None)
        if messages: await self._callback(messages, is_album=True)


class MessageProcessor:
    def __init__(self, client, source_channel, target_channel):
        self.client = client; self.source_channel = source_channel
        self.downloader = Downloader(client); self.publisher = Publisher(client, target_channel)

    async def process(self, messages, is_album=False):
        if not messages: return
        primary = sorted(messages, key=lambda m: m.id)[0]
        msg_id = primary.id
        db = await Database.get()
        if await db.is_processed(msg_id): return
        await db.save_message(source_message_id=msg_id, source_channel=self.source_channel, status="processing")
        raw_caption = primary.message or ""
        media_files, media_type, media_count = [], "text", 0
        if is_album:
            media_files = await self.downloader.download_album(messages); media_type = "album"; media_count = len(media_files)
        elif primary.media:
            mf = await self.downloader.download_media(primary); media_files = [mf] if mf else []; media_type = mf.media_type if mf else "text"; media_count = 1 if mf else 0
        caption_result = await process_caption(raw_caption, msg_id)
        processed_caption = caption_result.processed
        target_id = None
        try:
            if media_type == "album" and media_files: target_id = await self.publisher.publish_with_retry(self.publisher.publish_album, media_files, processed_caption)
            elif media_type == "photo" and media_files: target_id = await self.publisher.publish_with_retry(self.publisher.publish_photo, media_files[0], processed_caption)
            elif media_type in ("video", "document") and media_files: target_id = await self.publisher.publish_with_retry(self.publisher.publish_video, media_files[0], processed_caption)
            elif processed_caption: target_id = await self.publisher.publish_with_retry(self.publisher.publish_text, processed_caption)
            await db.save_message(source_message_id=msg_id, source_channel=self.source_channel, target_message_id=target_id, status="test" if Config.TEST_MODE else "success", original_caption=raw_caption, processed_caption=processed_caption, media_type=media_type, media_count=media_count)
        except Exception as e:
            await db.save_message(source_message_id=msg_id, source_channel=self.source_channel, status="failed", error_message=str(e))
        finally:
            for mf in media_files: mf.cleanup()
            await asyncio.sleep(Config.PUBLISH_DELAY)


class ChannelListener:
    def __init__(self, client, source_channel, target_channel):
        self.client = client; self.source_channel = source_channel
        self.processor = MessageProcessor(client, source_channel, target_channel)
        self.album_buffer = AlbumBuffer(timeout=Config.ALBUM_COLLECT_TIMEOUT, callback=self.processor.process)

    async def start(self):
        source_entity = await self.client.get_entity(self.source_channel)
        @self.client.on(events.NewMessage(chats=source_entity))
        async def on_new_message(event):
            msg = event.message
            if msg.grouped_id: self.album_buffer.add(msg)
            else: await self.processor.process([msg], is_album=False)
        await self.client.run_until_disconnected()
