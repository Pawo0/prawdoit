"""Select a few trusted topic links for the answer without influencing its verdict.

'Przydatne, zaufane strony' for the explanation page: at most 3 links that fit the claim's topic.

Keyword → topic map (topic vocabulary: docs/SOURCE_REGISTRY.md) → registry entries from data/sources/*.json whose
`topics` match. The registry is read tolerantly (other tools write it; broken or partial files are skipped), and a
small built-in list covers the topics when the registry has nothing yet. These links are pointers for the reader,
never evidence: they do not affect the verdict.

Reading guide: docs/backend/REQUEST_FLOW.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from .config import settings
from .schemas import CheckResult
from .textutil import short

log = logging.getLogger("prawdowid.resources")
MAX = 3

TOPIC_LABEL = {
    "podroze": "podróże",
    "pogoda": "pogoda",
    "woda_powodz": "powódź i stany wód",
    "drogi": "drogi",
    "kolej": "kolej",
    "lotnictwo": "lotnictwo",
    "morze": "morze",
    "transport": "transport",
    "zdrowie": "zdrowie",
    "zywnosc": "żywność",
    "promieniowanie": "promieniowanie",
    "powietrze": "jakość powietrza",
    "cyber": "cyberbezpieczeństwo",
    "oszustwa": "oszustwa",
    "bezpieczenstwo": "bezpieczeństwo",
    "obronnosc": "obronność",
    "pozary": "pożary",
    "prawo": "prawo",
    "statystyka": "statystyka",
    "finanse": "finanse",
    "wybory": "wybory",
    "ue": "Unia Europejska",
    "dezinformacja": "dezinformacja",
    "zagranica": "sprawy zagraniczne",
    "rzad": "rząd",
}

# Order = priority when several topics match equally often (more specific topics first).
_KW: list[tuple[str, str]] = [
    (
        "podroze",
        r"podróż\w*|strajk\w*|wyjazd\w*|wakacj\w*|urlop\w*|turyst\w*|wiz[aąy]\b|paszport\w*|odyseusz\w*|biur\w* podróży",
    ),
    (
        "pogoda",
        r"pogod\w*|burz\w*|upał\w*|mróz\w*|mroz\w*|śnie[gż]\w*|wichur\w*|orkan\w*|ulew\w*|imgw|huragan\w*|tornad\w*|gołoledź\w*",
    ),
    (
        "woda_powodz",
        r"powód\w*|powodz\w*|zalan\w*|zalew\w*|wezbra\w*|stan\w* wód|hydrolog\w*|wał\w* przeciwpowodz\w*|tam[aąy]\b",
    ),
    (
        "drogi",
        r"drog[aiy]\b|drogow\w*|autostrad\w*|ekspresówk\w*|gddkia|korek\w*|objazd\w*|fotoradar\w*|prawo jazdy|kierowc\w*",
    ),
    ("kolej", r"pociąg\w*|kolej\w*|pkp\w*|intercity|peron\w*|dworc\w*|dworzec"),
    (
        "lotnictwo",
        r"lotnisk\w*|samolot\w*|linie lotnicze|lot[uy]\b|odwołan\w* lot\w*|ulc\b|przestrze\w* powietrzn\w*",
    ),
    ("morze", r"morz\w*|morsk\w*|bałty\w*|żeglug\w*|statk\w*|statek|prom\w*\b|kąpielisk\w*"),
    (
        "transport",
        r"autobus\w*|tramwaj\w*|bilet\w*|komunikacj\w*|mpk|ztm|metr[oa]\b|przejazd\w*|transport\w*|pasażer\w*|jeździ\w*|jeźdz\w*",
    ),
    (
        "promieniowanie",
        r"promieniowa\w*|radioaktyw\w*|jądrow\w*|atomow\w*|jodek|jodu\b|czarnobyl\w*|zaporos\w*|zaporoż\w*",
    ),
    (
        "powietrze",
        r"smog\w*|jakoś\w* powietrza|pył\w* zawieszon\w*|pm ?10|pm ?2[,.]5|zanieczyszcze\w* powietrza",
    ),
    (
        "zywnosc",
        r"żywnoś\w*|jedzeni\w*|spożywcz\w*|wycofa\w* z (?:obrotu|sprzedaży)|salmonell\w*|listeri\w*|sanepid\w*|wod\w* pitn\w*|wod\w* z kranu",
    ),
    (
        "zdrowie",
        r"zdrowi\w*|szczepi\w*|chorob\w*|choroba|wirus\w*|epidemi\w*|pandemi\w*|covid\w*|gryp\w*|leki?\b|leków|szpital\w*|lekarz\w*|nfz|recept\w*|aptek\w*",
    ),
    (
        "cyber",
        r"hake\w*|haker\w*|cyber\w*|phishing\w*|wyciek\w* danych|ransomware|ddos|złośliw\w* oprogramow\w*",
    ),
    (
        "oszustwa",
        r"oszust\w*|oszuk\w*|wyłudz\w*|sms\w*|blik\w*|dopłat\w* do paczk\w*|fałszyw\w* (?:sklep|stron|link)\w*|podszyw\w*|scam\w*|kryptowalut\w*",
    ),
    ("pozary", r"pożar\w*|straż\w* pożarn\w*|psp\b|płonie|płonął|spłon\w*"),
    (
        "bezpieczenstwo",
        r"alarm\w*|ewakuac\w*|schron\w*|zagrożeni\w*|rcb\b|kryzys\w*|blackout\w*|sabota\w*|zamach\w*|terror\w*|syren\w*",
    ),
    (
        "obronnosc",
        r"wojsk\w*|armi[aię]\w*|mobilizac\w*|pob[oó]r\w*|nato\b|żołnierz\w*|\bmon\b|rakiet\w*|dron\w*|wojn\w*|zbrojeni\w*",
    ),
    ("wybory", r"wybor\w*|wyborcz\w*|głosowa\w*|referend\w*|pkw\b|kandydat\w*|frekwencj\w*"),
    (
        "ue",
        r"\bue\b|unia europejska|unii europejskiej|uni[ią] europejsk\w*|bruksel\w*|komisj\w* europejsk\w*|parlament\w* europejsk\w*|eurostat\w*|pakt\w* migracyjn\w*|dyrektyw\w*",
    ),
    (
        "prawo",
        r"ustaw\w*|przepis\w*|rozporządze\w*|kodeks\w*|zakaz\w*|dziennik\w* ustaw|sejm\w*|senat\w*|trybunał\w*|sąd\w*|kar[aąy]\b|mandat\w*",
    ),
    (
        "statystyka",
        r"gus\b|inflacj\w*|bezroboci\w*|wynagrodze\w*|płac[aey]\b|cen[aąy]\b|ceny|ludnoś\w*|demograf\w*|statysty\w*|pkb",
    ),
    (
        "finanse",
        r"nbp|kurs\w* (?:euro|dolara|walut|franka)|stop\w* procentow\w*|kredyt\w*|bank\w*|emerytur\w*|podat\w*|świadcze\w*|800 ?plus|zus\b|vat\b|budżet\w*|miliard\w*|mld\b",
    ),
    (
        "zagranica",
        r"za granic\w*|ambasad\w*|konsulat\w*|\bmsz\b|dyplomac\w*|włoch\w*|włosz\w*|niemc\w*|ukrain\w*|rosj\w*|białoru\w*|chin\w*|usa\b|ameryk\w*|franc\w*|hiszpan\w*|turcj\w*|egipt\w*|izrael\w*",
    ),
    (
        "dezinformacja",
        r"dezinform\w*|fake ?news\w*|propagand\w*|trol\w*|fałszyw\w* informac\w*|manipulac\w*",
    ),
    ("rzad", r"rząd\w*|rzęd\w*|premier\w*|minist\w*|prezydent\w*"),
]
_KW_RX = [(t, re.compile(rf"\b(?:{p})", re.I)) for t, p in _KW]
_ORDER = {t: i for i, (t, _) in enumerate(_KW)}

# Built-in fallback (organizers' list rules/resources.txt + well-known public services). Used when the registry has
# no entry for a topic. Same shape as registry entries (subset of fields).
FALLBACK: list[dict] = [
    {
        "name": "Informacje dla podróżujących (MSZ)",
        "url": "https://www.gov.pl/web/dyplomacja/informacje-dla-podrozujacych",
        "topics": ["podroze"],
        "tier": 1,
        "why": "Aktualne ostrzeżenia MSZ dla wyjeżdżających za granicę.",
    },
    {
        "name": "Odyseusz (MSZ)",
        "url": "https://odyseusz.gov.pl/",
        "topics": ["podroze"],
        "tier": 1,
        "why": "Rejestracja podróży i komunikaty konsularne MSZ.",
    },
    {
        "name": "Ministerstwo Spraw Zagranicznych",
        "url": "https://www.gov.pl/web/dyplomacja",
        "topics": ["zagranica"],
        "tier": 1,
        "why": "Oficjalne stanowiska i komunikaty polskiej dyplomacji.",
    },
    {
        "name": "CERT Polska",
        "url": "https://cert.pl/",
        "topics": ["cyber", "oszustwa"],
        "tier": 1,
        "why": "Ostrzeżenia przed oszustwami w sieci; podejrzany SMS prześlij na numer 8080.",
    },
    {
        "name": "IMGW — ostrzeżenia meteorologiczne",
        "url": "https://meteo.imgw.pl/",
        "topics": ["pogoda"],
        "tier": 1,
        "why": "Oficjalne prognozy i ostrzeżenia pogodowe.",
    },
    {
        "name": "IMGW — hydrologia",
        "url": "https://hydro.imgw.pl/",
        "topics": ["woda_powodz"],
        "tier": 1,
        "why": "Stany wód i ostrzeżenia hydrologiczne.",
    },
    {
        "name": "Ostrzeżenia RCB",
        "url": "https://www.gov.pl/web/gov/ostrzezenia",
        "topics": ["bezpieczenstwo", "pogoda", "woda_powodz"],
        "tier": 1,
        "why": "Ostrzeżenia Rządowego Centrum Bezpieczeństwa.",
    },
    {
        "name": "GIS — ostrzeżenia",
        "url": "https://www.gov.pl/web/gis/ostrzezenia",
        "topics": ["zywnosc", "zdrowie"],
        "tier": 1,
        "why": "Komunikaty Głównego Inspektoratu Sanitarnego (np. wycofane produkty).",
    },
    {
        "name": "Ministerstwo Zdrowia",
        "url": "https://www.gov.pl/web/zdrowie",
        "topics": ["zdrowie"],
        "tier": 1,
        "why": "Oficjalne komunikaty o zdrowiu i szczepieniach.",
    },
    {
        "name": "GDDKiA — informacje drogowe",
        "url": "https://drogi.gddkia.gov.pl/informacje-drogowe",
        "topics": ["drogi"],
        "tier": 1,
        "why": "Utrudnienia na drogach krajowych.",
    },
    {
        "name": "Portal Pasażera",
        "url": "https://portalpasazera.pl/",
        "topics": ["kolej"],
        "tier": 1,
        "why": "Rozkłady i utrudnienia na kolei.",
    },
    {
        "name": "ULC — prawa pasażera",
        "url": "https://ulc.gov.pl/prawa-pasazera",
        "topics": ["lotnictwo"],
        "tier": 1,
        "why": "Prawa pasażera w ruchu lotniczym.",
    },
    {
        "name": "UMS — warunki żeglugi",
        "url": "https://www.ums.gov.pl/bezpieczenstwo-morskie/warunki-zeglugi",
        "topics": ["morze"],
        "tier": 1,
        "why": "Komunikaty o bezpieczeństwie na morzu.",
    },
    {
        "name": "Ministerstwo Infrastruktury — prawa pasażerów",
        "url": "https://www.gov.pl/web/infrastruktura/prawa-pasazerow",
        "topics": ["transport", "kolej"],
        "tier": 1,
        "why": "Prawa pasażerów i infolinia dla obywatela.",
    },
    {
        "name": "GIOŚ — jakość powietrza",
        "url": "https://powietrze.gios.gov.pl/pjp/",
        "topics": ["powietrze"],
        "tier": 1,
        "why": "Pomiary jakości powietrza na żywo.",
    },
    {
        "name": "PAA — monitoring promieniowania",
        "url": "https://monitoring.paa.gov.pl/",
        "topics": ["promieniowanie"],
        "tier": 1,
        "why": "Pomiary promieniowania w Polsce na żywo.",
    },
    {
        "name": "Państwowa Straż Pożarna",
        "url": "https://www.gov.pl/web/kgpsp/aktualnosci",
        "topics": ["pozary"],
        "tier": 1,
        "why": "Komunikaty straży pożarnej.",
    },
    {
        "name": "Ministerstwo Obrony Narodowej",
        "url": "https://www.gov.pl/web/obrona-narodowa/aktualnosci5",
        "topics": ["obronnosc"],
        "tier": 1,
        "why": "Oficjalne komunikaty MON.",
    },
    {
        "name": "ISAP — Internetowy System Aktów Prawnych",
        "url": "https://isap.sejm.gov.pl/",
        "topics": ["prawo"],
        "tier": 1,
        "why": "Teksty ustaw i rozporządzeń (Dziennik Ustaw).",
    },
    {
        "name": "GUS — Główny Urząd Statystyczny",
        "url": "https://stat.gov.pl/",
        "topics": ["statystyka"],
        "tier": 1,
        "why": "Oficjalne dane statystyczne.",
    },
    {
        "name": "Ministerstwo Finansów",
        "url": "https://www.gov.pl/web/finanse",
        "topics": ["finanse"],
        "tier": 1,
        "kw": r"budżet|podat|vat|mld|miliard|dług",
        "why": "Budżet państwa, podatki — oficjalne dane i komunikaty.",
    },
    {
        "name": "NBP — kursy walut",
        "url": "https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/",
        "topics": ["finanse"],
        "tier": 1,
        "kw": r"kurs|walut|nbp|euro\b|dolar|frank|stop\w* procent",
        "why": "Kursy walut i dane Narodowego Banku Polskiego.",
    },
    {
        "name": "ZUS",
        "url": "https://www.zus.pl/",
        "topics": ["finanse"],
        "tier": 1,
        "kw": r"emerytur|rent[aęy]|świadcz|zus|zasił",
        "why": "Emerytury, renty i świadczenia — oficjalne informacje ZUS.",
    },
    {
        "name": "Państwowa Komisja Wyborcza",
        "url": "https://pkw.gov.pl/",
        "topics": ["wybory"],
        "tier": 1,
        "why": "Oficjalne informacje o wyborach i wynikach.",
    },
    {
        "name": "EUR-Lex",
        "url": "https://eur-lex.europa.eu/homepage.html?locale=pl",
        "topics": ["ue", "prawo"],
        "tier": 1,
        "why": "Oficjalne teksty prawa Unii Europejskiej.",
    },
    {
        "name": "Rząd RP — gov.pl",
        "url": "https://www.gov.pl/web/premier",
        "topics": ["rzad"],
        "tier": 1,
        "why": "Oficjalne komunikaty Kancelarii Premiera.",
    },
    {
        "name": "Demagog",
        "url": "https://demagog.org.pl/",
        "topics": ["dezinformacja"],
        "tier": 2,
        "why": "Polska organizacja fact-checkingowa (IFCN).",
    },
    {
        "name": "EUvsDisinfo",
        "url": "https://euvsdisinfo.eu/pl/",
        "topics": ["dezinformacja", "zagranica"],
        "tier": 2,
        "why": "Baza przypadków dezinformacji prowadzona przez UE.",
    },
    {
        "name": "NASK — zgłoś dezinformację",
        "url": "https://zglos-dezinformacje.nask.pl/",
        "topics": ["dezinformacja"],
        "tier": 1,
        "why": "Tu zgłosisz fałszywą informację w sieci.",
    },
]
_SKIP_METHODS = {"live_search", "google_factcheck"}
_WEAK = {
    "rzad"
}  # too broad in the registry (many entries list it) — use only the built-in link for this topic
_cache: tuple[tuple, list[dict]] | None = None


def topics_for(text: str, limit: int = 2) -> list[str]:
    counts = {t: len(rx.findall(text)) for t, rx in _KW_RX}
    hits = [t for t, n in counts.items() if n]
    hits.sort(key=lambda t: (-counts[t], _ORDER[t]))
    return hits[:limit]


def _registry() -> list[dict]:
    """All registry entries (tolerant: skips unreadable files; accepts a single object or a list per file)."""
    global _cache
    d = Path(settings.root) / "data" / "sources"
    try:
        files = sorted(d.glob("*.json"))
        sig = tuple((f.name, f.stat().st_mtime_ns) for f in files)
    except OSError:
        return []
    if _cache and _cache[0] == sig:
        return _cache[1]
    out: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        items = (
            data
            if isinstance(data, list)
            else data.get("sources", [data]) if isinstance(data, dict) else []
        )
        for s in items:
            if (
                isinstance(s, dict)
                and isinstance(s.get("url"), str)
                and s["url"].startswith("https://")
                and isinstance(s.get("topics"), list)
                and s.get("method") not in _SKIP_METHODS
            ):
                out.append(s)
    _cache = (sig, out)
    return out


def _why(s: dict, topic: str) -> str:
    if s.get("why"):
        return s["why"]
    q = re.split(r"[;:]|\.\s", str(s.get("qualification") or ""))[0].strip()
    if len(q) >= 15:
        return short(q, 100).rstrip(".…") + "."
    return f"Oficjalne informacje: {TOPIC_LABEL.get(topic, topic)} ({short(str(s.get('publisher') or ''), 60)})."


_GENERIC = {
    "ministerstwo",
    "przedstawicielstwo",
    "stowarzyszenie",
    "gov",
    "dane",
    "informacje",
    "państwowa",
    "rząd",
    "ostrzeżenia",
    "portal",
}


def _affinity(s: dict, text: str) -> bool:
    """Does the claim name this entry's institution or subject? (fallback `kw`, or an acronym / distinctive first
    word of the entry name: 'Według GUS…' → GUS, 'kurs euro w NBP' → NBP, 'Eurostatu' → Eurostat).
    """
    if s.get("kw") and re.search(s["kw"], text, re.I):
        return True
    name = f"{s.get('name', '')} {s.get('publisher', '')}"
    toks = set(re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ]{2,6}\b", name))
    first = re.split(r"[\s—–(.,-]+", str(s.get("name") or "").strip())[0]
    if len(first) >= 4 and first.lower() not in _GENERIC:
        toks.add(first)
    return any(re.search(rf"\b{re.escape(tok)}\w*", text, re.I) for tok in toks)


def _key(url: str) -> str:
    """One link per institution: the host, or host + /web/<unit> on gov.pl (each ministry is its own site there)."""
    u = urlparse(url)
    host = (u.hostname or "").removeprefix("www.")
    seg = [x for x in u.path.split("/") if x]
    return f"{host}/web/{seg[1]}" if host == "gov.pl" and len(seg) > 1 and seg[0] == "web" else host


def resources_for(res: CheckResult) -> list[dict]:
    """≤3 trusted pages for the topic of the checked claims: [{title, url, why}]."""
    if res.status != "ok" or not res.claims:
        return []
    text = " ".join(c.claim for c in res.claims)
    topics = topics_for(text) or ["dezinformacja"]
    if "dezinformacja" not in topics and any(
        c.verdict in ("falszywe", "wprowadzajace_w_blad") for c in res.claims
    ):
        topics.append(
            "dezinformacja"
        )  # known false/misleading claim → also where to check / report such content
    # do not repeat the main source as a "resource"
    used = {
        _key(c.evidence[c.main_evidence].url)
        for c in res.claims
        if c.main_evidence is not None and c.main_evidence < len(c.evidence)
    }
    reg = _registry()

    def ranked(t: str) -> list[dict]:
        def rank(s: dict) -> tuple:
            ts = s.get("topics") or []
            return (
                not _affinity(s, text),
                ts[:1] != [t],
                int(s.get("tier") or 9),
                s.get("_origin", 0),
                -len(set(ts) & set(topics)),
            )

        def fits(
            s: dict,
        ) -> bool:  # travel pages only for travel claims (registry tags them "zagranica" too)
            return "podroze" not in (s.get("topics") or []) or "podroze" in topics

        live = [
            s
            for s in reg
            if t in (s.get("topics") or [])
            and s.get("enabled", True) is not False
            and t not in _WEAK
        ]
        pool = live + [dict(s, _origin=1) for s in FALLBACK if t in s["topics"]]
        return sorted((s for s in pool if fits(s)), key=rank)

    per_topic = {1: MAX, 2: 2}.get(len(topics), 1)  # topics share the three slots
    picked: list[dict] = []
    for quota in (
        per_topic,
        MAX,
    ):  # first pass: quota per topic; second pass: fill the remaining slots
        for t in topics:
            taken = sum(1 for p in picked if p["topic"] == TOPIC_LABEL.get(t, t))
            for s in ranked(t):
                if len(picked) >= MAX or taken >= quota:
                    break
                k = _key(s["url"])
                if k in used:
                    continue
                used.add(k)
                taken += 1
                title = re.sub(
                    r"\s*\((?:serwer |interfejs )?(?:MCP|API)\b[^)]*\)",
                    "",
                    str(s.get("name") or s.get("publisher") or s["url"]),
                )
                picked.append(
                    {
                        "title": short(title, 80),
                        "url": s["url"],
                        "why": _why(s, t),
                        "topic": TOPIC_LABEL.get(t, t),
                    }
                )
    return picked
