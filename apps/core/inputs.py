"""Lecture securisee des nombres et telephones saisis par les utilisateurs.

Une saisie invalide (« abc », « 12,5 », « -3 », « 1e9 ») ne doit jamais lever
d'exception (erreur 500) ni devenir silencieusement un faux chiffre (0 FCFA).
"""
import re

PHONE_RE = re.compile(r"^\+?[0-9]{8,15}$")


def clean_int(raw, *, default=None, lo=None, hi=None):
    """Entier strict. Espaces ignores (« 1 500 » -> 1500). Invalide -> default.

    Hors bornes -> None si pas de default explicite, sinon default. Les appelants
    qui veulent un message d'erreur testent le retour None.
    """
    if raw is None:
        return default
    text = str(raw).strip().replace(" ", "").replace(" ", "").replace("\xa0", "")
    if not re.fullmatch(r"[+-]?\d{1,12}", text):
        return default
    value = int(text)
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        return default
    return value


def clean_float(raw, *, lo=None, hi=None):
    """Nombre decimal (GPS). Accepte la virgule. Invalide ou hors bornes -> None."""
    if raw in (None, ""):
        return None
    text = str(raw).strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    if value != value or value in (float("inf"), float("-inf")):  # NaN / infini
        return None
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        return None
    return value


def clean_phone(raw):
    """Telephone camerounais ou international : retourne la forme normalisee, sinon None."""
    if raw in (None, ""):
        return ""
    compact = re.sub(r"[ .\-()]", "", str(raw))
    return compact if PHONE_RE.match(compact) else None
