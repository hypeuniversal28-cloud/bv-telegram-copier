"""
Détection intelligente des contacts de commande dans les publications russes.
Remplace le username de commande par ORDER_ADMIN.
"""
import re
from modules.logger import log

# ── Mots-clés russes indiquant une action de commande / achat ─────────────
ORDER_KEYWORDS_RU = [
    # Commander
    "заказ", "заказать", "заказа", "заказе", "заказов", "заказывать",
    # Acheter
    "купить", "купите", "покупка", "покупайте",
    # Écrire / contacter
    "пишите", "напишите", "написать", "пиши",
    # Contacter
    "связаться", "свяжитесь", "обращайтесь",
    # Demander le prix
    "узнать цену", "уточнить цену", "по цене",
    # Contact / vendeur
    "продавец", "администратор", "менеджер", "оператор",
    # Réserver
    "бронь", "бронирование", "забронировать",
    # Questions / infos
    "вопросам", "информации", "подробности", "деталях",
    # Prix
    "стоимость", "цена",
]

# ── Patterns regex pour trouver un username dans un contexte de commande ──
ORDER_PATTERNS_RU = [
    # "для заказа пишите @username"  /  "для заказа: @username"
    re.compile(
        r"(?:для\s+)?(?:заказ[а-я]*|купить|покупки|бронирования)"
        r"[^\n@]{0,40}@([\w]+)",
        re.IGNORECASE,
    ),
    # "пишите @username"
    re.compile(
        r"(?:пиши(?:те)?|напишите|написать)[^\n@]{0,30}@([\w]+)",
        re.IGNORECASE,
    ),
    # "контакт: @username"  /  "контакты @username"
    re.compile(
        r"контакт[ыа]?\s*[:\-—]?\s*@([\w]+)",
        re.IGNORECASE,
    ),
    # "продавец: @username"  /  "менеджер @username"
    re.compile(
        r"(?:продавец|менеджер|администратор|оператор)\s*[:\-—]?\s*@([\w]+)",
        re.IGNORECASE,
    ),
    # "заказ: @username"  /  "заказать у @username"
    re.compile(
        r"заказ[а-я]*\s*[:\-—у]?\s*@([\w]+)",
        re.IGNORECASE,
    ),
    # "@username для заказа / по вопросам"
    re.compile(
        r"@([\w]+)\s+(?:для\s+)?(?:заказ[а-я]*|покупки|вопросов)",
        re.IGNORECASE,
    ),
    # "цена/заказ @username"
    re.compile(
        r"(?:цена|стоимость)\s*/?\s*(?:заказ[а-я]*)?\s*[:\-—]?\s*@([\w]+)",
        re.IGNORECASE,
    ),
    # "свяжитесь с @username"
    re.compile(
        r"(?:свяжитесь|связаться|обращайтесь)[^\n@]{0,30}@([\w]+)",
        re.IGNORECASE,
    ),
    # Fallback : "по вопросам @username"
    re.compile(
        r"по\s+вопросам\s+[^\n@]{0,20}@([\w]+)",
        re.IGNORECASE,
    ),
]


def _line_has_order_context(line: str) -> bool:
    """Vérifie si la ligne contient un mot-clé de commande en russe."""
    lower = line.lower()
    return any(kw in lower for kw in ORDER_KEYWORDS_RU)


def find_order_contacts(text: str) -> set[str]:
    """
    Analyse le texte et retourne l'ensemble des usernames (sans @)
    utilisés dans un contexte de commande/achat.
    """
    order_contacts: set[str] = set()

    lines = text.split("\n")
    for line in lines:
        # Chercher d'abord via les patterns structurés
        for pattern in ORDER_PATTERNS_RU:
            for match in pattern.finditer(line):
                username = match.group(1)
                order_contacts.add(username)
                log.debug(f"[ORDER CONTACT] Pattern trouvé : @{username} dans '{line.strip()}'")

        # Fallback : ligne avec mot-clé + username
        if _line_has_order_context(line):
            usernames_in_line = re.findall(r"@([\w]+)", line)
            for u in usernames_in_line:
                if u not in order_contacts:
                    order_contacts.add(u)
                    log.debug(f"[ORDER CONTACT] Contexte clé trouvé : @{u} dans '{line.strip()}'")

    return order_contacts


def replace_order_contacts(
    text: str,
    order_contacts: set[str],
    replacement: str = "bvOrderAdmin",
) -> tuple[str, list[tuple[str, str]]]:
    """
    Remplace les usernames de commande dans le texte.
    Retourne (texte_modifié, liste_des_remplacements).
    """
    replacements: list[tuple[str, str]] = []

    for username in order_contacts:
        # Remplacer @username (avec arobase) par le nom de remplacement
        pattern = re.compile(r"@" + re.escape(username), re.IGNORECASE)
        if pattern.search(text):
            text = pattern.sub(replacement, text)
            replacements.append((f"@{username}", replacement))
            log.info(f"[ORDER CONTACT] @{username} → {replacement}")

    return text, replacements


# ── Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    samples = [
        "Для заказа пишите @example_admin",
        "Заказать: @seller123",
        "Купить у @shopowner",
        "По вопросам заказа обращайтесь к @manager_bot",
        "@shop_contact для заказа",
        "Цена/заказ: @price_bot",
        "Size: M/L/XL",
        "السعر: 450 درهم",
    ]
    for s in samples:
        contacts = find_order_contacts(s)
        print(f"Input  : {s}")
        print(f"Trouvé : {contacts}")
        result, reps = replace_order_contacts(s, contacts)
        print(f"Résultat: {result}")
        print()
