"""
Traduction russe → arabe avec plusieurs backends (résilience).
Ordre de tentative : GoogleTranslator → MyMemoryTranslator → texte original.
Traitement ligne par ligne pour préserver la structure de la caption.
"""
import asyncio
import re
from modules.logger import log
from modules.language_detector import classify_line

# ── Placeholder pour protéger les usernames pendant la traduction ──────────
_USERNAME_RE = re.compile(r"@[\w]+")


def _protect_usernames(text: str) -> tuple[str, dict]:
    """
    Remplace @username par des placeholders numérotés.
    Retourne (texte protégé, dict {placeholder: username_original}).
    """
    mapping: dict[str, str] = {}
    counter = [0]

    def _replace(m: re.Match) -> str:
        ph = f"__USR{counter[0]}__"
        mapping[ph] = m.group(0)
        counter[0] += 1
        return ph

    return _USERNAME_RE.sub(_replace, text), mapping


def _restore_usernames(text: str, mapping: dict) -> str:
    """Remet les usernames originaux après traduction."""
    for ph, original in mapping.items():
        text = text.replace(ph, original)
    return text


# ── Backends de traduction ────────────────────────────────────────────────

def _try_google(text: str, source: str, target: str) -> str | None:
    """Tente une traduction via Google Translate (deep-translator)."""
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source=source, target=target).translate(text)
        return result if result else None
    except Exception as e:
        log.debug(f"[TRANSLATION] Google backend indisponible : {e}")
        return None


def _try_mymemory(text: str, source: str, target: str) -> str | None:
    """Tente une traduction via MyMemory (deep-translator)."""
    try:
        from deep_translator import MyMemoryTranslator
        # MyMemory utilise des codes régionaux : ru-RU, ar-SA
        src = f"{source}-{source.upper()}" if "-" not in source else source
        tgt = f"{target}-SA" if target == "ar" else (f"{target}-{target.upper()}" if "-" not in target else target)
        result = MyMemoryTranslator(source=src, target=tgt).translate(text)
        return result if result else None
    except Exception as e:
        log.debug(f"[TRANSLATION] MyMemory backend indisponible : {e}")
        return None


_backend_failed_logged: bool = False  # Log une seule fois par session


def _translate_sync(text: str, source: str = "ru", target: str = "ar") -> str:
    """
    Traduction synchrone (bloquante) avec fallback multi-backend.
    Appelée via run_in_executor pour ne pas bloquer la boucle asyncio.
    """
    global _backend_failed_logged

    if not text.strip():
        return text

    # Backend 1 : Google Translate
    result = _try_google(text, source, target)
    if result:
        _backend_failed_logged = False  # Reset si on réussit
        return result

    # Backend 2 : MyMemory
    result = _try_mymemory(text, source, target)
    if result:
        _backend_failed_logged = False
        return result

    # Fallback : texte original inchangé
    if not _backend_failed_logged:
        log.warning("[TRANSLATION] Backends indisponibles — texte original conservé (vérifiez la connexion).")
        _backend_failed_logged = True
    return text


async def translate_text(text: str, source: str = "ru", target: str = "ar") -> str:
    """Traduit un texte de manière asynchrone (non bloquant)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _translate_sync, text, source, target)


# ── Pipeline ligne par ligne ──────────────────────────────────────────────

async def translate_caption(
    caption: str,
    source_lang: str = "ru",
    target_lang: str = "ar",
) -> tuple[str, list[dict]]:
    """
    Traduit uniquement les lignes russes d'une caption.
    Préserve les lignes arabes, anglaises, chiffres, emojis, références.

    Retourne :
        (caption_traduite, liste_de_logs)

    Chaque log : {"original", "translated", "detected_language"}
    """
    if not caption:
        return caption, []

    lines = caption.split("\n")
    result_lines: list[str] = []
    translation_logs: list[dict] = []

    for line in lines:
        lang = classify_line(line)

        if lang in ("other", "ar"):
            # Déjà en arabe, ou sans cyrillique → conserver tel quel
            result_lines.append(line)
            continue

        if lang in ("ru", "mixed"):
            # Protéger les @usernames avant d'envoyer à l'API
            protected, mapping = _protect_usernames(line)

            translated = await translate_text(protected, source=source_lang, target=target_lang)

            # Restaurer les @usernames
            translated = _restore_usernames(translated, mapping)

            result_lines.append(translated)
            translation_logs.append({
                "original":          line,
                "translated":        translated,
                "detected_language": lang,
            })
            continue

        result_lines.append(line)

    return "\n".join(result_lines), translation_logs


# ── Test rapide ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _test():
        samples = [
            "Новая коллекция 🔥",
            "Цена: 3500 ₽",
            "Для заказа пишите @example_admin",
            "Size: S / M / L / XL",
            "السعر: 450 درهم",
        ]
        caption = "\n".join(samples)
        print("─" * 50)
        print("Input:")
        print(caption)
        print("─" * 50)
        translated, logs = await translate_caption(caption)
        print("Output:")
        print(translated)
        print("─" * 50)
        print("Logs:")
        for entry in logs:
            print(f"  [{entry['detected_language']}] {entry['original']!r}")
            print(f"       → {entry['translated']!r}")

    asyncio.run(_test())
