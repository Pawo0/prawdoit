"""SPRAWDŹ (NASK, kampania „Sprawdź, zanim udostępnisz”) — educational rhetoric signals.

These signals are PREBUNKING / media-literacy hints shown next to the result. By design they NEVER influence the
verdict (the challenge forbids judging truth by style, author, domain or popularity).
"""
from __future__ import annotations

import re

_SENS = re.compile(r"\b(szok\w*|pilne|uwaga|nie uwierzysz|przeraża\w*|wstrząs\w*|skandal\w*|sensac\w*|ujawnia\w*|"
                   r"tragedi\w*|katastrof\w*|horror|dramat\w*|alarm\w*|natychmiast)\b|!{2,}", re.I)
_PROV = re.compile(r"(udostępnij|przekaż dalej|roześlij|zanim usuną|zanim to usuną|media milczą|nikt (ci|wam) nie powie|"
                   r"obudźcie się|oni nie chcą|ukrywają|prawda, której|cenzur\w*|mainstream\w*|nie dajcie się)", re.I)
_DISC = re.compile(r"\b(zdrajc\w*|sprzedawczyk\w*|złodzie\w*|oszu[sś]\w*|band[aąy]\b|kłamc\w*|mafi\w*|okupan\w*|"
                   r"szkodni\w*|pasożyt\w*|agent\w* (kremla|rosji|niemiec|brukseli|ukrainy)|ruska onuca|onuc\w*|"
                   r"targowic\w*|lewactw\w*|faszyst\w*|banderow\w*)\b", re.I)
_SRC = re.compile(r"(według|wg\b|źródło:|jak podaje|jak podał|raport\w*|dane (gus|nbp|eurostat)|komunikat\w*|https?://)", re.I)


def _caps_ratio(text: str) -> float:
    words = [w for w in re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{4,}", text)]
    return sum(w.isupper() for w in words) / max(1, len(words))


def sprawdz_signals(text: str, kinds: list[str], url_meta: dict | None, archival: bool, sources_found: bool) -> list[dict]:
    out = []

    def add(letter, name, flagged, note, hits=None):
        out.append({"letter": letter, "name": name, "flagged": bool(flagged), "note": note,
                    "hits": sorted(set(h.lower() for h in (hits or [])))[:5]})

    sens = [m.group(0) for m in _SENS.finditer(text)]
    caps = _caps_ratio(text) > 0.3
    add("S", "Sensacyjność", sens or caps,
        "Język silnie emocjonalny — zatrzymaj się, zanim udostępnisz." if (sens or caps) else
        "Nie wykryto typowych zwrotów sensacyjnych.", sens)
    prov = [m.group(0) for m in _PROV.finditer(text)]
    add("P", "Prowokowanie", prov, "Treść nakłania do szybkiego udostępniania lub podważa zaufanie do innych źródeł."
        if prov else "Nie wykryto typowych zwrotów nakłaniających.", prov)
    mixed = "opinia" in kinds and "fakt" in kinds
    add("R", "Racjonalność", mixed, "Wiadomość miesza fakty z opiniami — oddzielamy je poniżej." if mixed else
        "Sprawdź, czy wnioski wynikają z podanych faktów.")
    author = (url_meta or {}).get("author") or (url_meta or {}).get("sitename")
    add("A", "Autor", not author, f"Strona podaje autora/wydawcę: {author}. Sprawdź, czy to rzeczywiście on."
        if author else "Brak informacji o autorze — sprawdź, kto jest źródłem tej treści.")
    add("W", "Wadliwy kontekst", archival, "Materiał może pochodzić z innego czasu niż sugeruje treść." if archival else
        "Sprawdź datę i miejsce — czy materiał nie pochodzi z innego wydarzenia?")
    disc = [m.group(0) for m in _DISC.finditer(text)]
    add("D", "Dyskredytacja", disc, "Treść używa obraźliwych etykiet wobec osób lub grup." if disc else
        "Nie wykryto typowych etykiet dyskredytujących.", disc)
    cites = bool(_SRC.search(text))
    add("Ź", "Źródła", not cites, ("Treść powołuje się na źródła — sprawdź, czy mówią to samo (porównaj poniżej)."
                                   if cites else "Treść nie wskazuje źródeł.") +
        (" Znaleźliśmy materiały źródłowe — zob. wyżej." if sources_found else ""))
    return out
