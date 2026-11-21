# Prawdowid — architektura

```
 KANAŁY (cienkie adaptery, bez logiki weryfikacji)            RDZEŃ WERYFIKACJI (jeden dla wszystkich kanałów)
 ┌──────────────────────────┐
 │ Strona WWW / PWA          │──┐   POST /api/check     ┌──────────────────────────────────────────────────┐
 │ (Web Share Target Android)│  │                       │ 1. Wejście: walidacja, limit, maskowanie PII     │
 ├──────────────────────────┤  │                       │    URL → bezpieczne pobranie (SSRF guard)        │
 │ Wtyczka przeglądarki      │──┤   POST /api/quick     │    + ekstrakcja treści (trafilatura)             │
 │ (Chrome/Edge/Vivaldi,     │  │   (szybka ścieżka)    │ 2. Skan prompt-injection → neutralizacja + log   │
 │  Firefox Android)         │  │                       │ 3. Twierdzenia: podział na zdania, fakty vs      │
 ├──────────────────────────┤  │                       │    opinie/prognozy, check-worthiness             │
 │ WhatsApp Cloud API webhook│──┤   /webhooks/whatsapp  │ 4. Wyszukiwanie hybrydowe: BM25 + embeddingi     │
 │ Messenger webhook         │──┤   /webhooks/messenger │    (mmlw-retrieval-e5-small) + dopasowanie do    │
 │ Adapter demo (czat WWW)   │──┤   (?demo=1)           │    twierdzeń już sprawdzonych (PFCR)             │
 │ Discord bot (proces)      │──┘   POST /api/chat-reply│ 5. Fragment dosłowny (bramka V2) + stanowisko:   │
 └──────────────────────────┘                          │    NLI mDeBERTa-v3 / reguła liczbowa (dane GUS…) │
                                                        │ 6. Werdykt: reguły R1–R6 (jawne, wersjonowane)   │
 ┌──────────────────────────┐                          │ 7. Wyjaśnienie z szablonu (opcj. LLM tylko       │
 │ Panel analityka           │◄── /api/cases ───────────│    upraszcza język; walidacja wyjścia)           │
 │ (sprawy, metryki, eksport)│                          │ 8. Zapis przebiegu (SQLite), sprawy moderatora   │
 └──────────────────────────┘                          └──────────────────────────────────────────────────┘
                                                                    ▲
 KORPUS (JSONL, jeden schemat)  ── ingest/*.py (harmonogram) ──────┘
   kat. A: MSZ/gov.pl, ISAP/ELI, EUR-Lex, GUS/BDL, NBP, Eurostat, PKW, RCB, CERT Polska
   kat. B: Demagog, FakeNews.pl, Stowarzyszenie Pravda, Konkret24, EUvsDisinfo, CheckFirst
```

## Przepływ danych
1. **Wejście** (tekst ≤ 6000 znaków lub URL). Dane osobowe (PESEL, telefon, e-mail, nr konta, nr dowodu) są maskowane
   przed zapisem. Strona z URL jest pobierana z ochroną SSRF (tylko publiczne IP, limity rozmiaru/czasu, ręczna obsługa
   przekierowań), treść traktowana jako **niezaufane dane**.
2. **Bezpieczeństwo**: wzorce poleceń (PL/EN, tokeny szablonów czatu, ukryte znaki) → zdarzenie `prompt_injection`
   w dzienniku + neutralizacja fragmentu. Instrukcje są kodem, treść jest danymi — żaden tekst nie zmienia reguł.
3. **Twierdzenia**: do 3 najbardziej „sprawdzalnych” zdań (liczby, nazwy własne, czasowniki faktów); opinie i prognozy
   → „nie podlega weryfikacji”; pytania („Czy…?”) zamieniane na twierdzenia.
4. **Wyszukiwanie**: hybryda BM25 (prosty stemming prefiksowy dla polskiego) + gęste embeddingi, fuzja RRF; osobny
   indeks twierdzeń sprawdzonych przez fact-checkerów (dopasowanie semantyczne, próg 0,82 lub 0,74 + NLI).
5. **Dowody**: dla każdego źródła wybierany jest 1–2-zdaniowy fragment najbardziej zbieżny z twierdzeniem; ten sam
   fragment jest cytowany i oceniany. Cytat musi występować dosłownie w źródle (bramka V2). Stanowisko: NLI (≥ 0,70)
   albo deterministyczne porównanie liczb z kartą danych urzędowych dla tego samego okresu. Fact-check: werdykt
   organizacji + kontrola, czy użytkownik nie twierdzi czegoś przeciwnego (NLI sprzeczności → odwrócenie oceny).
6. **Werdykt**: reguły R1–R6 (opis: `/metodologia`), siła podstaw jako tekst (mocna/umiarkowana), przesłanki,
   kody przyczyn wstrzymania, „co mogłoby to rozstrzygnąć”, ostrzeżenie o materiale archiwalnym.
7. **Pętla informacji**: nierozstrzygnięte twierdzenia faktyczne i tematy wysokiego ryzyka z jednym źródłem →
   sprawa w kolejce analityka; podobne zgłoszenia (cos ≥ 0,86) łączone w jedną sprawę z licznikiem i priorytetem.
8. **Audyt**: każde sprawdzenie (ID, czas, kanał, zamaskowane wejście, źródła, werdykty, czasy etapów, modele,
   wersja reguł, zdarzenia bezpieczeństwa) w SQLite; retencja 30 dni; usuwanie sesji; eksport CSV/JSON.

## Szybka ścieżka wtyczki (`/api/quick`)
Wtyczka wysyła **tylko tekst** widocznych postów/nagłówków (bez URL strony, bez ciasteczek, bez identyfikatora
użytkownika), paczkami co ~0,5 s. Serwer: embedding zdań → najbliższe twierdzenie ocenione jako fałsz /
manipulacja → NLI (czy to samo twierdzenie, a nie zaprzeczenie) → prawdopodobieństwo powtórzenia obalonej
informacji = σ(30·(cos − 0,80)) × zgodność NLI × waga oceny. Wynik cache'owany po haszu tekstu.
≥ 0,60 → zasłona „kliknij, aby odsłonić”; 0,35–0,60 → odznaka z procentem; poniżej — nic (unikamy ogólnych
ostrzeżeń, które obniżają zaufanie do prawdziwych informacji).

## Modele i dostawcy (wszystko lokalnie, CPU)
| Rola | Model | Licencja | Uwagi |
|---|---|---|---|
| Embeddingi (wyszukiwanie, dopasowanie twierdzeń) | `sdadas/mmlw-retrieval-e5-small` | Apache-2.0 | polski, 33M param. backbone; fp32 na CPU (wagi fp16 są ~15× wolniejsze) |
| Stanowisko (NLI) | `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | MIT | wielojęzyczny, zawiera polski |
| LLM (opcjonalnie) | dowolny OpenAI-compatible: Bielik / PLLuM przez llama.cpp lub vLLM, Mistral (UE) | — | tylko upraszczanie języka; wyłączony domyślnie |

Wymiana modelu = zmiana zmiennej środowiskowej (`PRAWDOWID_EMBED_MODEL`, `PRAWDOWID_NLI_MODEL`, `PRAWDOWID_LLM_*`).
Kanały, korpus i reguły są niezależne od modelu.

## Najważniejsze ograniczenia
- Zamknięty katalog źródeł: brak wyniku ≠ prawda/fałsz; nowe wydarzenia (< kilka godzin) zwykle → „brak dowodów”.
- NLI na CPU jest słabe w porównywaniu liczb i dat — dlatego reguła liczbowa dla kart danych urzędowych.
- Dopasowanie do fact-checków działa na poziomie twierdzeń; satyra, ironia i bardzo krótkie posty mogą być mylone.
- Facebook/X zmieniają strukturę DOM — adaptery wtyczki wymagają utrzymania (fallback: przycisk „Wybierz fragment”).
- OCR zrzutów ekranu i odwrotne wyszukiwanie obrazów nie są włączone (komunikowane jako ograniczenie techniczne).
