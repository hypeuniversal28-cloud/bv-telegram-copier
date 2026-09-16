"""
Détection de langue.
"""
import re

RE_CYRILLIC = re.compile(r"[а-яА-ЯсЁ]")
RE_ARABIC = re.compile(r"[؀-ٿ]")


def has_cyrillic(text): return bool(RE_CYRILLIC.search(text))
def has_arabic(text): return bool(RE_ARABIC.search(text))


def detect_languages(text):
    langs = []
    if has_cyrillic(text): langs.append("ru")
    if has_arabic(text): langs.append("ar")
    return langs


def classify_line(line):
    s = line.strip()
    if not s: return "other"
    cyr = has_cyrillic(s); ara = has_arabic(s)
    if cyr and ara: return "mixed"
    if cyr: return "ru"
    if ara: return "ar"
    return "other"
