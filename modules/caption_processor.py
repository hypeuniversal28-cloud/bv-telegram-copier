"""
Pipeline complet de traitement d'une caption :
  1. Détection des contacts de commande (avant traduction)
  2. Traduction russe → arabe (ligne par ligne)
  3. Remplacement des contacts de commande
  4. Log de chaque opération
"""
from config import Config
from modules.logger import log
from modules.language_detector import detect_languages, has_cyrillic
from modules.translator import translate_caption
from modules.order_detector import find_order_contacts, replace_order_contacts
from modules.database import Database


class CaptionResult:
    def __init__(
        self,
        original: str,
        processed: str,
        detected_languages: list[str],
        order_contacts: set[str],
        order_replacements: list[tuple[str, str]],
        translation_logs: list[dict],
    ):
        self.original = original
        self.processed = processed
        self.detected_languages = detected_languages
        self.order_contacts = order_contacts
        self.order_replacements = order_replacements
        self.translation_logs = translation_logs

    @property
    def was_translated(self) -> bool:
        return "ru" in self.detected_languages

    @property
    def had_order_replacement(self) -> bool:
        return bool(self.order_replacements)


async def process_caption(
    caption: str | None,
    message_id: int,
    persist_logs: bool = True,
) -> CaptionResult:
    """
    Traite une caption complète et retourne un CaptionResult.

    - caption        : texte brut de la publication source
    - message_id     : ID Telegram du message source (pour les logs DB)
    - persist_logs   : si True, enregistre les logs en base de données
    """
    if not caption:
        return CaptionResult(
            original="",
            processed="",
            detected_languages=[],
            order_contacts=set(),
            order_replacements=[],
            translation_logs=[],
        )

    original = caption
    detected_langs = detect_languages(caption)
    log.info(f"[LANGUAGE] Langues détectées : {detected_langs or ['aucune']}")

    # ── Étape 1 : Détecter les contacts de commande dans le texte russe ──
    order_contacts: set[str] = set()
    if "ru" in detected_langs:
        order_contacts = find_order_contacts(caption)
        if order_contacts:
            log.info(f"[ORDER CONTACT] Contacts trouvés : {order_contacts}")

    # ── Étape 2 : Traduction russe → arabe ───────────────────────────────
    translated_text = caption
    translation_logs: list[dict] = []

    if "ru" in detected_langs:
        log.info(f"[TRANSLATION] Russian → Arabic en cours…")
        translated_text, translation_logs = await translate_caption(
            caption,
            source_lang=Config.SOURCE_LANG,
            target_lang=Config.TARGET_LANG,
        )

        if translation_logs:
            for tl in translation_logs:
                log.debug(
                    f"[TRANSLATION]  {tl['original'][:60]!r}"
                    f" → {tl['translated'][:60]!r}"
                )

    # ── Étape 3 : Remplacement des contacts de commande ──────────────────
    final_text = translated_text
    order_replacements: list[tuple[str, str]] = []

    if order_contacts:
        final_text, order_replacements = replace_order_contacts(
            translated_text,
            order_contacts,
            replacement=Config.ORDER_ADMIN,
        )
        for orig, repl in order_replacements:
            log.info(f"[ORDER CONTACT] {orig} → {repl}")

    # ── Étape 4 : Persistance des logs ───────────────────────────────────
    if persist_logs:
        db = await Database.get()

        for tl in translation_logs:
            await db.save_translation(
                source_message_id=message_id,
                line_original=tl["original"],
                line_translated=tl["translated"],
                detected_language=tl["detected_language"],
            )

        for orig_user, repl in order_replacements:
            await db.save_order_replacement(
                source_message_id=message_id,
                original_username=orig_user,
                replaced_with=repl,
            )

    return CaptionResult(
        original=original,
        processed=final_text,
        detected_languages=detected_langs,
        order_contacts=order_contacts,
        orderReplacements=order_replacements,
        translation_logs=translation_logs,
    )
