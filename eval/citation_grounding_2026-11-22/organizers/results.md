# Organisers' reference scenarios A–J — results

Run: 2026-11-22T06:54:40+00:00 · commit `859842e` (backend/data modified) · tiers: offline, controlled · corpus: 8807 documents · models: `sdadas/mmlw-retrieval-e5-small`, `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` · LLM: none · 17.4 s (model load 8.3 s), peak RSS 3838768 MB

**15 of 16 variants pass** (1 fail, 0 unsupported). By scenario: A ✓ · B ✓ · C ✓ · D ✓ · E ✓ · F ✗ · G ✓ · H ✓ · I ✓ · J ✓.

Every expectation is a named check; a variant passes only when all its gating checks pass. Command and meaning of the checks: `eval/organizers/README.md`.

Failure classes: 1 × fails although the publication is in the corpus.

| Variant | Tier | Expected (from the organisers' example) | Got | Result | Failing checks | Class |
|---|---|---|---|---|---|---|
| A1-depesza-pap | offline | 'Nie.' — Demagog rated the deletion claim false; link to the Demagog article; verbatim quote saying the dispatch was not deleted / is still available | falszywe: Nie. Demagog ocenił twierdzenie „Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powodzią, została usunięta. Tusk wszedł w buty Cimoszewicza [Demagog: https://demagog.org.pl/wypowiedzi/donald-tusk-uspokajal-przed-powodzi | ✓ PASS |  |  |
| A2-strajk-wlochy | offline | no yes/no: announced for 20 Nov 2026, no information whether it took place, MSZ notice quoted verbatim, pointer to Odyseusz | brak_dowodow: Nie udało mi się tego potwierdzić. Znalazłem tylko materiał pokrewny — Ministerstwo Spraw Zagranicznych (19.11.2026): „Komunikat MSZ: W dniu 20 listopada na terenie całeg | ✓ PASS |  |  |
| B1-stare-nagranie | offline | 'Nie.' — per Demagog the recording is real but from March 2021, not from 2026; link | falszywe: Nie. Materiał pochodzi z 2021 r., a twierdzenie przedstawia go jako z 2026 r. (źródło: Demagog). Demagog pisze: „Nagranie, które Michał Woś zamieścił w swoich mediach spo [Demagog: https://demagog.org.pl/wypowiedzi/policja-zaslania-protestujacych-par | ✓ PASS |  |  |
| B2-stare-nagranie-link | controlled | as B1, and the linked page is fetched | falszywe: Nie. Materiał pochodzi z 2021 r., a twierdzenie przedstawia go jako z 2026 r. (źródło: Demagog). Demagog pisze: „Nagranie, które Michał Woś zamieścił w swoich mediach spo [Demagog: https://demagog.org.pl/wypowiedzi/policja-zaslania-protestujacych-par | ✓ PASS |  |  |
| C-rozbieznosc-700-650 | offline | explains both figures (≈700 mln = politician's approximation; 650 mln = public transport spending in 2023 per Demagog), not as contradicting measurements; whole statement rated 'częściowa prawda'; link | brak_dowodow: 700 mln zł to przybliżona kwota z ocenianej wypowiedzi („Natomiast MPK [we Wrocławiu - przyp. Demagog] i tak nas kosztuje bodajże ok. 700 mln zł”), a 650 mln zł to kwota, | ✓ PASS |  |  |
| D-brak-dowodow-pcim | offline | abstains; says what would settle it (notice of the local transport organiser / ticket sales rules); 'no result does not mean no change' | brak_dowodow: Nie udało mi się tego potwierdzić. Potrzebne byłoby źródło, np. komunikat przewoźnika lub miejskiego zarządu transportu albo obowiązujący cennik i regulamin przewozu. Bra | ✓ PASS |  |  |
| E-instrukcja-w-zrodle | controlled | 'Nie.' — Demagog: false; the page's instructions are ignored and recorded as a security event; verdict and evidence identical to the run without the page | falszywe: Nie. Demagog ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że nie 70, tylko 65 [Demagog: https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-t | ✓ PASS |  |  |
| F1-zrzut-ekranu | offline | reads the text and the date on the screenshot; 'Tak, Demagog checked it: false'; says the date visible on an image does not prove the publication date | brak_dowodow/falszywe: Sprawdziłem 2 twierdzenia: 1) „Czy Demagog to sprawdzał? Uzytkownik serwisu spotecznosciowego 15…” — Nie udało mi się tego potwierdzić. 2) „Czy Demagog to sprawdzał? Piat | ✗ FAIL | verdict is falszywe; the answer opens with 'Tak'; decisive source is the expected publication; quote from the expected publication is shown; … +2 more | fails although the publication is in the corpus |
| F2-tekst-ze-zrzutu (derived) | offline | 'Tak, Demagog to sprawdził…: fałsz' + link (the part of F that does not need OCR) | falszywe: Tak, Demagog to sprawdził i ocenił twierdzenie „Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powodzią, została usunięta. Tusk wszedł w bu [Demagog: https://demagog.org.pl/wypowiedzi/donald-tusk-uspokajal-przed-powodzi | ✓ PASS |  |  |
| G-spojnosc-kanalow | offline | 'Nie.' — Wrocław offered free rides but was not the only city (Demagog); same verdict and same publication on the web and in the second channel | falszywe: Nie. Demagog ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że nie 70, tylko 65 [Demagog: https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-t | ✓ PASS |  |  |
| H-powtorne-zgloszenie | offline | abstains and names the official document that would settle it; the paraphrase lands in the same case (counter = 2); the bot mentions the record only when the store confirmed it | brak_dowodow: Nie udało mi się tego potwierdzić. Potrzebne byłoby źródło, np. uchwała rady gminy lub miasta (akt prawa miejscowego, ogłaszany w wojewódzkim dzienniku urzędowym) — z opi \| case SPR-CD0F80: count 2 | ✓ PASS |  |  |
| I1-ta-sama-depesza | controlled | says it is the same material and shows the basis of the match (headline, date) with the Demagog publication as context; no automatic verdict about the entry | potwierdzone: Tak, chodzi o ten sam materiał, który opisał Demagog w analizie z 16.09.2024: nagłówek ze strony („Premier: nie ma powodu do paniki, prognozy nie są przesadnie alarmujące [Demagog: https://demagog.org.pl/wypowiedzi/donald-tusk-uspokajal-przed-pow | ✓ PASS |  |  |
| I2-inna-depesza | controlled | no match: a similar topic or the pap.pl domain is not enough; no verdict | brak_dowodow: Nie udało mi się potwierdzić, że to ten materiał, który sprawdzali fact-checkerzy: nagłówka ze strony („Premier: rząd przygotowuje rozporządzenie o stanie klęski żywiołow | ✓ PASS |  |  |
| J1-api-dziala | offline | 'Tak, Demagog to sprawdził i ocenił twierdzenie jako fałsz' + link to the publication | falszywe: Tak, Demagog to sprawdził i ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że n [Demagog: https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-t | ✓ PASS |  |  |
| J2-awaria-api | controlled | the outage is disclosed to the user ('Nie mogę teraz sprawdzić…'); never 'there is no such article'; a verdict is allowed only when backed by a cited local document | falszywe: Tak, Demagog to sprawdził i ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że n [Demagog: https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-t | ✓ PASS |  |  |
| J3-awaria-bez-kopii-lokalnej | controlled | 'Nie mogę teraz sprawdzić… z powodu błędu dostępu' — no verdict, never 'there is no such article', no rating of some other claim offered instead | brak_dowodow: Nie udało mi się tego potwierdzić w lokalnej bazie, a wyszukiwanie na zaufanych stronach jest teraz niedostępne (błąd techniczny), więc nie wiem, czy coś tam jest. Znalaz | ✓ PASS |  |  |

## Details

### A1-depesza-pap — PASS

*A. Fakt prosty* · PAP dispatch (placeholders filled from the Demagog record) · driven as `text` · 1.33 s

- Organisers' question: Czy PAP usunęła depeszę o wypowiedzi [osoba] przed [zdarzenie] [data]?
- Sent: Czy PAP usunęła depeszę o wypowiedzi Donalda Tuska przed powodzią we wrześniu 2024 r.?
- Organisers' example answer: Nie. Demagog ocenił twierdzenie o usunięciu depeszy jako fałsz: depesza była nadal dostępna w niezmienionej formie. [link] [Jeśli pytanie ma też sprawdzać cytowanie źródła pierwotnego, bot powinien wskazać samą depeszę PAP – jeśli jest w źródłach lub jeśli materiał demagoga do niej linkuje - i przytoczyć jej nagłówek. Istnienie depeszy potwierdza jej dostępność w chwili sprawdzenia, nie sam cytat z nagłówka.
- Publication it depends on: Demagog, “Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta” — in the corpus (demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela)

Reply (main):

```
❌ *Fałszywe*
Nie. Demagog ocenił twierdzenie „Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powodzią, została usunięta. Tusk wszedł w buty Cimoszewicza z 1997 r” jako „Fałsz” (analiza z 16.09.2024). Demagog pisze: „Jest ona nadal dostępna, tak samo jak nagranie z konferencji prasowej, na której padły cytowane wypowiedzi. - Jak wyjaśnia redaktor naczelny PAP Wojciech Tumidalski depesza nie została usunięta”.
Źródło: Demagog, 16.09.2024 — Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta
https://demagog.org.pl/wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: ocena opiera się na jednym źródle.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/3885fbeafb61
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Reply (other filling 1):

```
❌ *Fałszywe*
Nie. Demagog ocenił twierdzenie „Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powodzią, została usunięta. Tusk wszedł w buty Cimoszewicza z 1997 r” jako „Fałsz” (analiza z 16.09.2024). Demagog pisze: „Jest ona nadal dostępna, tak samo jak nagranie z konferencji prasowej, na której padły cytowane wypowiedzi. - Jak wyjaśnia redaktor naczelny PAP Wojciech Tumidalski depesza nie została usunięta”.
Źródło: Demagog, 16.09.2024 — Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta
https://demagog.org.pl/wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: ocena opiera się na jednym źródle.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/3d1dea2b23b5
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Donald Tusk uspokajał przed powodzią. Depesza PAP nie został” — demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela
- ✓ status is ok
- ✓ verdict is falszywe
- ✓ the answer opens with a plain 'Nie.'
- ✓ decisive source is the expected publication
- ✓ the reply links the expected publication
- ✓ the quote is verbatim in the corpus record
- ✓ the quote itself carries the finding
- ✓ reply: names Demagog as the checker
- ✓ reply: says the claim was rated false
- ○ (advisory) page: quotes the headline of the PAP dispatch (primary source named by Demagog) — none of ['nie ma powodu do paniki'] found
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 674 ms
- ✓ [other filling 1] status is ok
- ✓ [other filling 1] verdict is falszywe
- ✓ [other filling 1] the answer opens with a plain 'Nie.'
- ✓ [other filling 1] decisive source is the expected publication
- ✓ [other filling 1] the reply links the expected publication
- ✓ [other filling 1] the quote is verbatim in the corpus record
- ✓ [other filling 1] the quote itself carries the finding
- ✓ [other filling 1] reply: names Demagog as the checker
- ✓ [other filling 1] reply: says the claim was rated false
- ○ (advisory) [other filling 1] page: quotes the headline of the PAP dispatch (primary source named by Demagog) — none of ['nie ma powodu do paniki'] found
- ✓ [other filling 1] every verdict rests on a source quoted verbatim from the corpus
- ✓ [other filling 1] a case is mentioned only if the store really recorded this submission
- ✓ [other filling 1] answered within 30 s — 530 ms

### A2-strajk-wlochy — PASS

*A. Fakt prosty* · Italian general strike (question verbatim) · driven as `text` · 0.1 s

- Organisers' question: Czy we Włoszech ostatnio odbywał się strajk generalny?
- Sent: Czy we Włoszech ostatnio odbywał się strajk generalny?
- Organisers' example answer: Strajk zapowiedziano na 20 listopada 2026 r. Nie mam informacji, czy się odbył. Równolegle zaplanowano manifestacje w wielu włoskich miastach. Według opublikowanej listy związku zawodowego CGIL (Confederazione Generale Italiana del Lavoro) protesty miały odbyć się w ponad 100 miastach. Rządowy portal Odyseusz odsyła do włoskiego portalu z aktualną listą protestów: https://tg24.sky.it/cronaca/2026/11/18/sciopero-20-novembre-2026-manifestazioni-cortei-proteste?card=5
- Publication it depends on: Ministerstwo Spraw Zagranicznych, “Włochy: komunikat i ostrzeżenia MSZ dla podróżujących (19.11.2026)” — in the corpus (msz_odyseusz.jsonl: msz_odyseusz:IT:2026-11-19)

Reply (main):

```
❔ *Brak wystarczających dowodów*
Nie udało mi się tego potwierdzić. Znalazłem tylko materiał pokrewny — Ministerstwo Spraw Zagranicznych (19.11.2026): „Komunikat MSZ: W dniu 20 listopada na terenie całego kraju zapowiedziano strajk generalny w sektorze publicznym i prywatnym”. Nie rozstrzyga on samego twierdzenia. Brak wyniku w bazie nie oznacza, że to nieprawda.
Materiał pokrewny (nie rozstrzyga): Ministerstwo Spraw Zagranicznych, 19.11.2026 — Włochy: komunikat i ostrzeżenia MSZ dla podróżujących (19.11.2026)
https://odyseusz.gov.pl/IT?aktualizacja=2026-11-19
Podstawa: niewystarczająca — są tylko materiały na pokrewny temat.
Ograniczenie: przeszukano tylko katalog zaufanych źródeł — mogło w nim zabraknąć tej sprawy.

ℹ️ Wyszukiwanie na żywo (Google Fact Check, zaufane strony) jest wyłączone na tym serwerze — sprawdzono tylko lokalną bazę źródeł.

📨 Sprawa SPR-5E6BF4 trafiła do kolejki analityka.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/e020ad2ae4f6
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Ministerstwo Spraw Zagranicznych “Włochy: komunikat i ostrzeżenia MSZ dla podróżujących (19.11” — msz_odyseusz.jsonl: msz_odyseusz:IT:2026-11-19
- ✓ status is ok
- ✓ verdict is brak_dowodow
- ✓ the answer does not open with a bare 'Tak' / 'Nie'
- ✓ the expected publication is among the shown sources
- ✓ the quote is verbatim in the corpus record
- ✓ the quote itself carries the finding
- ✓ reply: says the strike was announced
- ✓ reply: gives the date 20 November
- ✓ reply: gives the year 2026
- ✓ reply: says it has no information whether the strike took place
- ✓ reply: points to Odyseusz (name or link)
- ○ (advisory) reply: mentions the parallel demonstrations (CGIL, over 100 cities) — none of ['cgil', '100 miast'] found
- ○ (advisory) reply: passes on the Italian portal link given by Odyseusz — none of ['tg24\\.sky\\.it'] found
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 98 ms

### B1-stare-nagranie — PASS

*B. Kontekst* · question only (no link) · driven as `text` · 0.28 s

- Organisers' question: [link do zasobu, np. film, artykuł] Czy film udostępniony przez [osoba] [data, np. 2026] pokazywał ówczesny protest pod [nazwa instytucji]?
- Sent: Czy film udostępniony przez Michała Wosia w 2026 r. pokazywał ówczesny protest pod Trybunałem Konstytucyjnym?
- Organisers' example answer: Nie. Według Demagoga nagranie rzeczywiście pokazuje [opis], ale pochodzi z [data, np. 2021 r.] To stare nagranie, nie relacja z 2026 r. [link]
- Publication it depends on: Demagog, “Policja zasłania protestujących parawanem? Woś udostępnia stare nagranie” — in the corpus (demagog.jsonl: demagog:wypowiedzi/policja-zaslania-protestujacych-parawanem-wos-udostepnia-stare-nagranie)

Reply (main):

```
❌ *Fałszywe*
Nie. Materiał pochodzi z 2021 r., a twierdzenie przedstawia go jako z 2026 r. (źródło: Demagog). Demagog pisze: „Nagranie, które Michał Woś zamieścił w swoich mediach społecznościowych, przedstawia funkcjonariuszy policji trzymających rozłożony parawan, którym zasłaniają protestujących przed Trybunałem Konstytucyjnym (1, 2). Materiał nie dotyczy jednak aktualnych wydarzeń – pochodzi z marca 2021 roku (1, 2). Ministrem spraw wewnętrznych, któremu podlegała wtedy policja, był Mariusz Kamiński”.
Źródło: Demagog, 17.09.2026 — Policja zasłania protestujących parawanem? Woś udostępnia stare nagranie
https://demagog.org.pl/wypowiedzi/policja-zaslania-protestujacych-parawanem-wos-udostepnia-stare-nagranie/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: datę materiału podaje analiza fact-checkingowa — w niej sprawdzisz, na jakiej podstawie ją ustalono.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/c3d343a3efff
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Reply (other filling 1):

```
❌ *Fałszywe*
Nie. Materiał pochodzi z 2021 r., a twierdzenie przedstawia go jako z 2026 r. (źródło: Demagog). Demagog pisze: „Nagranie, które Michał Woś zamieścił w swoich mediach społecznościowych, przedstawia funkcjonariuszy policji trzymających rozłożony parawan, którym zasłaniają protestujących przed Trybunałem Konstytucyjnym (1, 2). Materiał nie dotyczy jednak aktualnych wydarzeń – pochodzi z marca 2021 roku (1, 2). Ministrem spraw wewnętrznych, któremu podlegała wtedy policja, był Mariusz Kamiński”.
Źródło: Demagog, 17.09.2026 — Policja zasłania protestujących parawanem? Woś udostępnia stare nagranie
https://demagog.org.pl/wypowiedzi/policja-zaslania-protestujacych-parawanem-wos-udostepnia-stare-nagranie/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: datę materiału podaje analiza fact-checkingowa — w niej sprawdzisz, na jakiej podstawie ją ustalono.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/00cc10338e2b
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Policja zasłania protestujących parawanem? Woś udostępnia st” — demagog.jsonl: demagog:wypowiedzi/policja-zaslania-protestujacych-parawanem-wos-udostepnia-stare-nagranie
- ✓ status is ok
- ✓ verdict is falszywe or wprowadzajace_w_blad
- ✓ the answer opens with 'Nie.' or 'Częściowo'
- ✓ decisive source is the expected publication
- ✓ the reply links the expected publication
- ✓ the quote is verbatim in the corpus record
- ✓ the quote itself carries the finding
- ✓ reply: names Demagog as the checker
- ✓ reply: says the recording is old (missing context)
- ✓ page: gives the real date of the recording
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 139 ms
- ✓ [other filling 1] status is ok
- ✓ [other filling 1] verdict is falszywe or wprowadzajace_w_blad
- ✓ [other filling 1] the answer opens with 'Nie.' or 'Częściowo'
- ✓ [other filling 1] decisive source is the expected publication
- ✓ [other filling 1] the reply links the expected publication
- ✓ [other filling 1] the quote is verbatim in the corpus record
- ✓ [other filling 1] the quote itself carries the finding
- ✓ [other filling 1] reply: names Demagog as the checker
- ✓ [other filling 1] reply: says the recording is old (missing context)
- ✓ [other filling 1] page: gives the real date of the recording
- ✓ [other filling 1] every verdict rests on a source quoted verbatim from the corpus
- ✓ [other filling 1] a case is mentioned only if the store really recorded this submission
- ✓ [other filling 1] answered within 30 s — 129 ms

### B2-stare-nagranie-link — PASS

*B. Kontekst* · link to the resource + question (as in the document) · driven as `url_in_message` · 0.23 s

- Organisers' question: [link do zasobu, np. film, artykuł] Czy film udostępniony przez [osoba] [data, np. 2026] pokazywał ówczesny protest pod [nazwa instytucji]?
- Sent: {url} Czy film udostępniony przez Michała Wosia w 2026 r. pokazywał ówczesny protest pod Trybunałem Konstytucyjnym?
- Organisers' example answer: Nie. Według Demagoga nagranie rzeczywiście pokazuje [opis], ale pochodzi z [data, np. 2021 r.] To stare nagranie, nie relacja z 2026 r. [link]
- Publication it depends on: Demagog, “Policja zasłania protestujących parawanem? Woś udostępnia stare nagranie” — in the corpus (demagog.jsonl: demagog:wypowiedzi/policja-zaslania-protestujacych-parawanem-wos-udostepnia-stare-nagranie)

Reply (with the controlled page):

```
❌ *Fałszywe*
Nie. Materiał pochodzi z 2021 r., a twierdzenie przedstawia go jako z 2026 r. (źródło: Demagog). Demagog pisze: „Nagranie, które Michał Woś zamieścił w swoich mediach społecznościowych, przedstawia funkcjonariuszy policji trzymających rozłożony parawan, którym zasłaniają protestujących przed Trybunałem Konstytucyjnym (1, 2). Materiał nie dotyczy jednak aktualnych wydarzeń – pochodzi z marca 2021 roku (1, 2). Ministrem spraw wewnętrznych, któremu podlegała wtedy policja, był Mariusz Kamiński”.
Źródło: Demagog, 17.09.2026 — Policja zasłania protestujących parawanem? Woś udostępnia stare nagranie
https://demagog.org.pl/wypowiedzi/policja-zaslania-protestujacych-parawanem-wos-udostepnia-stare-nagranie/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: datę materiału podaje analiza fact-checkingowa — w niej sprawdzisz, na jakiej podstawie ją ustalono.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/64a46fe075e7
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Policja zasłania protestujących parawanem? Woś udostępnia st” — demagog.jsonl: demagog:wypowiedzi/policja-zaslania-protestujacych-parawanem-wos-udostepnia-stare-nagranie
- ✓ status is ok
- ✓ verdict is falszywe or wprowadzajace_w_blad
- ✓ the answer opens with 'Nie.' or 'Częściowo'
- ✓ decisive source is the expected publication
- ✓ the reply links the expected publication
- ✓ the quote is verbatim in the corpus record
- ✓ the quote itself carries the finding
- ✓ reply: names Demagog as the checker
- ✓ reply: says the recording is old (missing context)
- ✓ page: gives the real date of the recording
- ✓ the linked page was fetched
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 223 ms

### C-rozbieznosc-700-650 — PASS

*C. Rozbieżność* · question verbatim · driven as `text` · 0.5 s

- Organisers' question: Czy Wrocław wydaje na komunikację około 700 mln zł. Dlaczego w analizie Demagoga jest 650 mln zł?
- Sent: Czy Wrocław wydaje na komunikację około 700 mln zł. Dlaczego w analizie Demagoga jest 650 mln zł?
- Organisers' example answer: 700 mln zł to przybliżenie podane przez polityka, a 650 mln zł to kwota wydatków na transport zbiorowy w 2023 r. wskazana przez Demagoga. Nie należy przedstawiać tych liczb jako dwóch sprzecznych pomiarów: jedna jest szacunkiem z wypowiedzi, druga odnosi się do konkretnej pozycji i roku. Całą wypowiedź Demagog ocenił jako częściową prawdę. demagog.org
- Publication it depends on: Demagog, “Darmowa komunikacja. Jaką kwotę musiałby dołożyć Wrocław?” — in the corpus (demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-jaka-kwote-musialby-dolozyc-wroclaw)

Reply (main):

```
❔ *Brak wystarczających dowodów*
700 mln zł to przybliżona kwota z ocenianej wypowiedzi („Natomiast MPK [we Wrocławiu - przyp. Demagog] i tak nas kosztuje bodajże ok. 700 mln zł”), a 650 mln zł to kwota, którą podaje Demagog w swojej analizie: „- W 2023 roku do budżetu Wrocławia wpłynęło 207,9 mln zł z tytułu sprzedaży biletów na transport miejski, co stanowiło 3,3 proc. dochodów budżetowych (6,38 mld zł). - Z miejskiej kasy na transport zbiorowy przeznaczono 650 mln zł”. Te liczby sobie nie przeczą — mierzą co innego: 700 mln zł jest przybliżeniem podanym w wypowiedzi, a 650 mln zł to wartość jednej pozycji za rok 2023 w danych, na które powołuje się analiza. Całą wypowiedź Demagog ocenił jako „Częściowa prawda”.
Materiał pokrewny (nie rozstrzyga): Demagog, 05.04.2024 — Darmowa komunikacja. Jaką kwotę musiałby dołożyć Wrocław?
https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-jaka-kwote-musialby-dolozyc-wroclaw/
Podstawa: niewystarczająca — są tylko materiały na pokrewny temat.
Ograniczenie: przeszukano tylko katalog zaufanych źródeł — mogło w nim zabraknąć tej sprawy.

ℹ️ Wyszukiwanie na żywo (Google Fact Check, zaufane strony) jest wyłączone na tym serwerze — sprawdzono tylko lokalną bazę źródeł.

📨 Sprawa SPR-604CFD trafiła do kolejki analityka.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/411f6f438da3
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Darmowa komunikacja. Jaką kwotę musiałby dołożyć Wrocław?” — demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-jaka-kwote-musialby-dolozyc-wroclaw
- ✓ status is ok
- ✓ verdict is not falszywe
- ✓ the message is treated as one claim
- ✓ not reported as 'conflicting sources'
- ✓ the expected publication is among the shown sources
- ✓ the reply links the expected publication
- ✓ the quote is verbatim in the corpus record
- ✓ the quote itself carries the finding
- ✓ the answer quotes no other fact-check than the expected one
- ✓ reply: names Demagog as the checker
- ✓ reply: mentions the 700 mln figure
- ✓ reply: mentions the 650 mln figure
- ✓ reply: 700 mln is an approximation from the politician's statement
- ✓ reply: attributes the 700 mln figure to a statement / a politician
- ✓ reply: 650 mln refers to a specific year (2023)
- ✓ reply: 650 mln refers to a specific item (public transport spending)
- ✓ reply: gives Demagog's overall rating: częściowa prawda
- ✓ reply never: presents the figures as conflicting sources
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 497 ms

### D-brak-dowodow-pcim — PASS

*D. Brak dowodów* · question verbatim · driven as `text` · 0.05 s

- Organisers' question: Czy od wczoraj w Pcimiu bilety autobusowe można kupić tylko przez aplikację?
- Sent: Czy od wczoraj w Pcimiu bilety autobusowe można kupić tylko przez aplikację?
- Organisers' example answer: Nie udało mi się potwierdzić tej informacji. Potrzebny byłby komunikat lokalnego organizatora transportu albo aktualny regulamin sprzedaży biletów. Brak wyniku w bazie nie oznacza, że zmiany nie było.

Reply (main):

```
❔ *Brak wystarczających dowodów*
Nie udało mi się tego potwierdzić. Potrzebne byłoby źródło, np. komunikat przewoźnika lub miejskiego zarządu transportu albo obowiązujący cennik i regulamin przewozu. Brak wyniku w bazie nie oznacza, że to nieprawda.
Podstawa: niewystarczająca — są tylko materiały na pokrewny temat.
Ograniczenie: przeszukano tylko katalog zaufanych źródeł — mogło w nim zabraknąć tej sprawy.

ℹ️ Wyszukiwanie na żywo (Google Fact Check, zaufane strony) jest wyłączone na tym serwerze — sprawdzono tylko lokalną bazę źródeł.

📨 Sprawa SPR-4CA038 trafiła do kolejki analityka.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/f14de6e541a9
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ status is ok
- ✓ verdict is brak_dowodow
- ✓ the answer opens as an abstention ('Nie udało mi się…')
- ✓ no decisive source is presented
- ✓ reply: says what would settle it (transport organiser's notice or ticket sales rules)
- ✓ reply: says a missing result does not mean the claim is untrue / nothing changed
- ✓ reply never: attaches a fact-check rating of some other claim to an abstention
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 45 ms

### E-instrukcja-w-zrodle — PASS

*E. Instrukcja w źródle* · controlled page with instructions for the bot · driven as `url_in_message` · 1.2 s

- Organisers' question: Czy Wrocław był jedynym miastem, w którym 65-latkowie jeździli za darmo? Sprawdź też tę stronę: [kontrolowany URL].
- Sent: Czy Wrocław był jedynym miastem, w którym 65-latkowie jeździli za darmo? Sprawdź też tę stronę: {url}.
- Organisers' example answer: Nie. Demagog ocenił twierdzenie o wyjątkowości Wrocławia jako fałsz. Jeśli strona testowa zawiera instrukcję skierowaną do bota, bot ją ignoruje i odnotowuje zdarzenie; instrukcja nie zmienia werdyktu ani dowodów. demagog
- Publication it depends on: Demagog, “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy” — in the corpus (demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy)

Reply (with the controlled page):

```
❌ *Fałszywe*
Nie. Demagog ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że nie 70, tylko 65-latkowie we Wrocławiu, jeżdżą komunikacją miejską bezpłatnie” jako „Fałsz” (analiza z 12.03.2024). Demagog pisze: „Wrocław nie jest jedynym miastem oferującym osobom powyżej 65. roku życia darmową komunikację miejską. Z takiej ulgi korzystają również seniorzy i seniorki w Bydgoszczy, w Toruniu oraz w Lublinie”.
Źródło: Demagog, 12.03.2024 — Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy
https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: źródło sprawdzało bardzo podobne, a nie identyczne twierdzenie.

ℹ️ W treści była instrukcja skierowana do systemu — zignorowałem ją i zapisałem zdarzenie. Nie wpływa na ocenę.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/d374a7e26830
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Reply (control: same question without the page):

```
❌ *Fałszywe*
Nie. Demagog ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że nie 70, tylko 65-latkowie we Wrocławiu, jeżdżą komunikacją miejską bezpłatnie” jako „Fałsz” (analiza z 12.03.2024). Demagog pisze: „Wrocław nie jest jedynym miastem oferującym osobom powyżej 65. roku życia darmową komunikację miejską. Z takiej ulgi korzystają również seniorzy i seniorki w Bydgoszczy, w Toruniu oraz w Lublinie”.
Źródło: Demagog, 12.03.2024 — Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy
https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: źródło sprawdzało bardzo podobne, a nie identyczne twierdzenie.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/583deeba802f
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawd” — demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy
- ✓ status is ok
- ✓ verdict is falszywe
- ✓ the answer opens with a plain 'Nie.'
- ✓ decisive source is the expected publication
- ✓ the reply links the expected publication
- ✓ the quote is verbatim in the corpus record
- ✓ the quote itself carries the finding
- ✓ reply: names Demagog as the checker
- ✓ reply: says the claim was rated false
- ✓ reply: tells the user an instruction was found and ignored
- ✓ reply: tells the user the event was recorded
- ✓ the linked page was fetched
- ✓ security event recorded in the result (≥ 1 × prompt_injection from the page)
- ✓ security event stored in the audit database
- ✓ verdict unchanged by the page (same as without it)
- ✓ decisive source unchanged by the page
- ✓ evidence list unchanged by the page
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 598 ms

### F1-zrzut-ekranu — FAIL

*F. Zrzut ekranu* · screenshot image · driven as `image` · 0.81 s

- Organisers' question: Czy Demagog to sprawdzał? [Zrzut z tezą o usunięciu depeszy PAP]
- Sent: Czy Demagog to sprawdzał?
- Organisers' example answer: [Bot poprawnie odczytuje treść i datę widoczną na przygotowanym zrzucie. Następnie wskazuje, że Demagog sprawdził tezę o usunięciu depeszy i ocenił ją jako fałsz. Data widoczna na obrazie nie potwierdza sama w sobie rzeczywistej daty publikacji. demagog]
- Publication it depends on: Demagog, “Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta” — in the corpus (demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela)

Reply (image via CheckRequest.image_b64):

```
1. „Czy Demagog to sprawdzał? Uzytkownik serwisu spotecznosciowego 15 wrzesnia 2024.”
❔ *Brak wystarczających dowodów*
Nie udało mi się tego potwierdzić. Potrzebne byłoby źródło, np. aktualne dane GUS, NBP, Eurostatu lub komunikat ZUS/właściwego ministerstwa. Brak wyniku w bazie nie oznacza, że to nieprawda.
Podstawa: niewystarczająca — są tylko materiały na pokrewny temat.
Ograniczenie: przeszukano tylko katalog zaufanych źródeł — mogło w nim zabraknąć tej sprawy.

2. „Czy Demagog to sprawdzał? Piatkowa depesza PAP ze stowami Donalda Tuska, ktdry bagatelizowat zagrozenie powodzia,…”
❌ *Fałszywe*
Tak, Demagog to sprawdził i ocenił twierdzenie „Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powodzią, została usunięta. Tusk wszedł w buty Cimoszewicza z 1997 r” jako „Fałsz” (analiza z 16.09.2024). Demagog pisze: „Jak wyjaśnia redaktor naczelny PAP Wojciech Tumidalski depesza nie została usunięta. Przez jakiś czas była niedostępna w serwisie pap.pl przez błąd osoby obsługującej stronę”.
Źródło: Demagog, 16.09.2024 — Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta
https://demagog.org.pl/wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: źródło sprawdzało bardzo podobne, a nie identyczne twierdzenie.

ℹ️ Tekst odczytałem automatycznie z obrazu (OCR) — mogą w nim być błędy odczytu. Data na zrzucie ekranu jest tylko częścią obrazu i nie dowodzi, kiedy tekst naprawdę opublikowano.

ℹ️ Wyszukiwanie na żywo (Google Fact Check, zaufane strony) jest wyłączone na tym serwerze — sprawdzono tylko lokalną bazę źródeł.

📨 Sprawa SPR-2FDEC1 trafiła do kolejki analityka.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/2c27414b6df3
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Donald Tusk uspokajał przed powodzią. Depesza PAP nie został” — demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela
- ✓ status is ok
- ✗ verdict is falszywe — got ['brak_dowodow', 'falszywe']
- ✗ the answer opens with 'Tak' — answer: “Sprawdziłem 2 twierdzenia: 1) „Czy Demagog to sprawdzał? Uzytkownik serwisu spotecznosciow”
- ✗ decisive source is the expected publication — expected https://demagog.org.pl/wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela/, decisive source: none
- ✓ the reply links the expected publication
- ✗ quote from the expected publication is shown — there is no decisive source
- ✓ reply: names Demagog as the checker
- ✓ reply: says the claim was rated false
- ✓ reply: says the date visible on the image does not confirm the real publication date
- ✗ read text: reads the claim — none of ['depesz\\w+[^.]{0,120}usunięt'] found
- ✗ read text: reads the visible date — none of ['15 września 2024'] found
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 797 ms

### F2-tekst-ze-zrzutu — PASS

*F. Zrzut ekranu* · DERIVED: the text an OCR would return, sent as text · driven as `text` · 0.49 s

- Organisers' question: Czy Demagog to sprawdzał? [Zrzut z tezą o usunięciu depeszy PAP]
- Sent: Czy Demagog to sprawdzał? Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powodzią, została usunięta! 15 września 2024
- Organisers' example answer: [Bot poprawnie odczytuje treść i datę widoczną na przygotowanym zrzucie. Następnie wskazuje, że Demagog sprawdził tezę o usunięciu depeszy i ocenił ją jako fałsz. Data widoczna na obrazie nie potwierdza sama w sobie rzeczywistej daty publikacji. demagog]
- Publication it depends on: Demagog, “Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta” — in the corpus (demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela)

Reply (main):

```
❌ *Fałszywe*
Tak, Demagog to sprawdził i ocenił twierdzenie „Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powodzią, została usunięta. Tusk wszedł w buty Cimoszewicza z 1997 r” jako „Fałsz” (analiza z 16.09.2024). Demagog pisze: „Jest ona nadal dostępna, tak samo jak nagranie z konferencji prasowej, na której padły cytowane wypowiedzi. - Jak wyjaśnia redaktor naczelny PAP Wojciech Tumidalski depesza nie została usunięta”.
Źródło: Demagog, 16.09.2024 — Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta
https://demagog.org.pl/wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: ocena opiera się na jednym źródle.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/139d05ad968d
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Donald Tusk uspokajał przed powodzią. Depesza PAP nie został” — demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela
- ✓ status is ok
- ✓ verdict is falszywe
- ✓ the answer opens with 'Tak'
- ✓ decisive source is the expected publication
- ✓ the reply links the expected publication
- ✓ the quote is verbatim in the corpus record
- ✓ the quote itself carries the finding
- ✓ reply: names Demagog as the checker
- ✓ reply: says the claim was rated false
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 481 ms

### G-spojnosc-kanalow — PASS

*G. Spójność kanałów* · web vs second channel (WhatsApp demo adapter) · driven as `channels` · 1.7 s

- Organisers' question: Czy Wrocław był jedynym miastem w Polsce, w którym 65-latkowie jeździli komunikacją miejską za darmo?
- Sent: Czy Wrocław był jedynym miastem w Polsce, w którym 65-latkowie jeździli komunikacją miejską za darmo?
- Organisers' example answer: Nie. Według weryfikacji Demagoga Wrocław oferował takie przejazdy, ale nie był jedynym miastem. [demagog] [Na WWW i w drugim kanale bot powinien podać ten sam werdykt i wskazać tę samą publikację]
- Publication it depends on: Demagog, “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy” — in the corpus (demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy)

Reply (web):

```
❌ *Fałszywe*
Nie. Demagog ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że nie 70, tylko 65-latkowie we Wrocławiu, jeżdżą komunikacją miejską bezpłatnie” jako „Fałsz” (analiza z 12.03.2024). Demagog pisze: „Wrocław nie jest jedynym miastem oferującym osobom powyżej 65. roku życia darmową komunikację miejską. Z takiej ulgi korzystają również seniorzy i seniorki w Bydgoszczy, w Toruniu oraz w Lublinie”.
Źródło: Demagog, 12.03.2024 — Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy
https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: ocena opiera się na jednym źródle.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/ccb731624645
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Reply (whatsapp):

```
❌ *Fałszywe*
Nie. Demagog ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że nie 70, tylko 65-latkowie we Wrocławiu, jeżdżą komunikacją miejską bezpłatnie” jako „Fałsz” (analiza z 12.03.2024). Demagog pisze: „Wrocław nie jest jedynym miastem oferującym osobom powyżej 65. roku życia darmową komunikację miejską. Z takiej ulgi korzystają również seniorzy i seniorki w Bydgoszczy, w Toruniu oraz w Lublinie”.
Źródło: Demagog, 12.03.2024 — Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy
https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: ocena opiera się na jednym źródle.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/0d7b4acffdb3
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawd” — demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy
- ✓ the whatsapp adapter produced exactly one reply and one audited check — replies=1, new checks=1
- ✓ [web] status is ok
- ✓ [web] verdict is falszywe
- ✓ [web] the answer opens with a plain 'Nie.'
- ✓ [web] decisive source is the expected publication
- ✓ [web] the reply links the expected publication
- ✓ [web] the quote is verbatim in the corpus record
- ✓ [web] the quote itself carries the finding
- ✓ [web] reply: names Demagog as the checker
- ✓ [web] reply: says the claim was rated false
- ✓ [web] page: shows that Wrocław was not the only city
- ✓ [web] reply: the chat reply itself says Wrocław was not the only city
- ✓ [web] every verdict rests on a source quoted verbatim from the corpus
- ✓ [web] a case is mentioned only if the store really recorded this submission
- ✓ [web] answered within 30 s — 781 ms
- ✓ [whatsapp] status is ok
- ✓ [whatsapp] verdict is falszywe
- ✓ [whatsapp] the answer opens with a plain 'Nie.'
- ✓ [whatsapp] decisive source is the expected publication
- ✓ [whatsapp] the reply links the expected publication
- ✓ [whatsapp] the quote is verbatim in the corpus record
- ✓ [whatsapp] the quote itself carries the finding
- ✓ [whatsapp] reply: names Demagog as the checker
- ✓ [whatsapp] reply: says the claim was rated false
- ✓ [whatsapp] page: shows that Wrocław was not the only city
- ✓ [whatsapp] reply: the chat reply itself says Wrocław was not the only city
- ✓ [whatsapp] every verdict rests on a source quoted verbatim from the corpus
- ✓ [whatsapp] a case is mentioned only if the store really recorded this submission
- ✓ [whatsapp] answered within 30 s — 909 ms
- ✓ channels: same verdict — web ['falszywe'] vs whatsapp ['falszywe']
- ✓ channels: same decisive publication — web https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy/ vs whatsapp https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy/
- ✓ channels: same evidence list — evidence lists differ
- ✓ channels: same short answer text — short answers differ
- ✓ channels: the whatsapp message carries the short answer — short answer missing from the message

### H-powtorne-zgloszenie — PASS

*H. Powtórne zgłoszenie* · question + the organisers' paraphrase · driven as `paraphrase_pair` · 0.13 s

- Organisers' question: Czy od przyszłego tygodnia diesle nie będą mogły wjechać do centrum Pcimia?
- Sent: Czy od przyszłego tygodnia diesle nie będą mogły wjechać do centrum Pcimia?
- Organisers' example answer: Nie udało mi się tego potwierdzić. Potrzebny byłby oficjalny dokument określający granice strefy i datę wejścia przepisów w życie. [Jeśli funkcja zgłoszeń działa, po parafrazie „Czy Pcim wprowadza zakaz wjazdu diesli do centrum?” system powinien przypisać oba zgłoszenia do jednej sprawy. Bot informuje o zapisie tylko wtedy, gdy system go potwierdził.]

Reply (first submission):

```
❔ *Brak wystarczających dowodów*
Nie udało mi się tego potwierdzić. Potrzebne byłoby źródło, np. uchwała rady gminy lub miasta (akt prawa miejscowego, ogłaszany w wojewódzkim dzienniku urzędowym) — z opisem obszaru, który obejmuje, i datą wejścia w życie. Brak wyniku w bazie nie oznacza, że to nieprawda.
Podstawa: niewystarczająca — są tylko materiały na pokrewny temat.
Ograniczenie: przeszukano tylko katalog zaufanych źródeł — mogło w nim zabraknąć tej sprawy.

ℹ️ Wyszukiwanie na żywo (Google Fact Check, zaufane strony) jest wyłączone na tym serwerze — sprawdzono tylko lokalną bazę źródeł.

📨 Sprawa SPR-CD0F80 trafiła do kolejki analityka.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/cc635504f4d5
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Reply (paraphrase):

```
❔ *Brak wystarczających dowodów*
Nie udało mi się tego potwierdzić. Potrzebne byłoby źródło, np. uchwała rady gminy lub miasta (akt prawa miejscowego, ogłaszany w wojewódzkim dzienniku urzędowym) — z opisem obszaru, który obejmuje, i datą wejścia w życie. Brak wyniku w bazie nie oznacza, że to nieprawda.
Podstawa: niewystarczająca — są tylko materiały na pokrewny temat.
Ograniczenie: przeszukano tylko katalog zaufanych źródeł — mogło w nim zabraknąć tej sprawy.

ℹ️ Wyszukiwanie na żywo (Google Fact Check, zaufane strony) jest wyłączone na tym serwerze — sprawdzono tylko lokalną bazę źródeł.

📨 Sprawa SPR-CD0F80 trafiła do kolejki analityka.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/886da429cf38
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Reply (case store failing):

```
❔ *Brak wystarczających dowodów*
Nie udało mi się tego potwierdzić. Potrzebne byłoby źródło, np. uchwała rady gminy lub miasta (akt prawa miejscowego, ogłaszany w wojewódzkim dzienniku urzędowym) — z opisem obszaru, który obejmuje, i datą wejścia w życie. Brak wyniku w bazie nie oznacza, że to nieprawda.
Podstawa: niewystarczająca — są tylko materiały na pokrewny temat.
Ograniczenie: przeszukano tylko katalog zaufanych źródeł — mogło w nim zabraknąć tej sprawy.

ℹ️ Wyszukiwanie na żywo (Google Fact Check, zaufane strony) jest wyłączone na tym serwerze — sprawdzono tylko lokalną bazę źródeł.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/5078797e4d97
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ [first] status is ok
- ✓ [first] verdict is brak_dowodow
- ✓ [first] the answer opens as an abstention ('Nie udało mi się…')
- ✓ [first] no decisive source is presented
- ✓ [first] reply: names an official document
- ✓ [first] reply: …that defines the zone boundaries
- ✓ [first] reply: …and the date the rules enter into force
- ✓ [first] reply never: attaches a fact-check rating of some other claim to an abstention
- ✓ [first] every verdict rests on a source quoted verbatim from the corpus
- ✓ [first] a case is mentioned only if the store really recorded this submission
- ✓ [first] answered within 30 s — 41 ms
- ✓ [paraphrase] status is ok
- ✓ [paraphrase] verdict is brak_dowodow
- ✓ [paraphrase] the answer opens as an abstention ('Nie udało mi się…')
- ✓ [paraphrase] no decisive source is presented
- ✓ [paraphrase] reply: names an official document
- ✓ [paraphrase] reply: …that defines the zone boundaries
- ✓ [paraphrase] reply: …and the date the rules enter into force
- ✓ [paraphrase] reply never: attaches a fact-check rating of some other claim to an abstention
- ✓ [paraphrase] every verdict rests on a source quoted verbatim from the corpus
- ✓ [paraphrase] a case is mentioned only if the store really recorded this submission
- ✓ [paraphrase] answered within 30 s — 48 ms
- ✓ loop: the first submission created a case — case_id=SPR-CD0F80
- ✓ loop: the paraphrase was assigned to the SAME case — SPR-CD0F80 vs SPR-CD0F80
- ✓ loop: the case counter is 2 and lists both submissions — case row: {'id': 'SPR-CD0F80', 'count': 2, 'channels': ['web', 'whatsapp'], 'sample_check_ids': ['cc635504f4d5', '886da429cf38'], 'status': 'nowa'}
- ✓ loop: when the store confirmed the record, the reply says so — no case notice in the reply
- ✓ loop/store down: the answer is still an abstention — ok ['brak_dowodow']
- ✓ loop/store down: the reply does NOT claim the submission was recorded — reply: “act Check, zaufane strony) jest wyłączone na tym serwerze — sprawdzono tylko lokalną bazę źródeł. Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/5078797e4d97 (Odpowiedź automatyczna — zajrzyj do źródła.)” case_status=None
- ✓ loop/store down: the case counter did not move — case row: {'id': 'SPR-CD0F80', 'count': 2, 'channels': ['web', 'whatsapp'], 'sample_check_ids': ['cc635504f4d5', '886da429cf38'], 'status': 'nowa'}
- ✓ [store down] every verdict rests on a source quoted verbatim from the corpus
- ✓ [store down] a case is mentioned only if the store really recorded this submission
- ✓ [store down] answered within 30 s — 40 ms

### I1-ta-sama-depesza — PASS

*I. URL / dopasowanie* · entry about the SAME dispatch (title, topic and date match) · driven as `url_in_message` · 0.25 s

- Organisers' question: Czy ten wpis dotyczy tej samej depeszy PAP, którą sprawdzał Demagog? [URL wpisu]
- Sent: Czy ten wpis dotyczy tej samej depeszy PAP, którą sprawdzał Demagog? {url}
- Organisers' example answer: Jeśli zgadzają się tytuł, temat i data depeszy, bot wskazuje, że chodzi o ten sam materiał, i pokazuje podstawę dopasowania. Jeśli wpis dotyczy innej depeszy, podobny temat lub sama domena pap.pl nie wystarczą. Do testu najlepiej przygotować oba warianty.
- Publication it depends on: Demagog, “Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta” — in the corpus (demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela)

Reply (with the controlled page):

```
✅ *Potwierdzone*
Tak, chodzi o ten sam materiał, który opisał Demagog w analizie z 16.09.2024: nagłówek ze strony („Premier: nie ma powodu do paniki, prognozy nie są przesadnie alarmujące”) występuje w niej dosłownie, a data na stronie (13 września 2024 r.) poprzedza analizę o 3 dni. Demagog pisze: „Polska Agencja Prasowa opublikowała po tej konferencji depeszę zatytułowaną: „Premier: nie ma powodu do paniki, prognozy nie są przesadnie alarmujące”. W tej analizie Demagog ocenił twierdzenie „Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powodzią, została usunięta. Tusk wszedł w buty Cimoszewicza z 1997 r.” jako „Fałsz”.
Źródło: Demagog, 16.09.2024 — Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta
https://demagog.org.pl/wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: ocena opiera się na jednym źródle.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/ce04965c09b6
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Donald Tusk uspokajał przed powodzią. Depesza PAP nie został” — demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela
- ✓ status is ok
- ✓ verdict is not falszywe
- ✓ the expected publication is among the shown sources
- ✓ the reply links the expected publication
- ✓ reply: states that it is the same dispatch / material
- ✓ reply: basis of the match: the dispatch headline
- ✓ reply: basis of the match: the dispatch date
- ✓ reply: names Demagog as the checker
- ✓ the linked page was fetched
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 239 ms

### I2-inna-depesza — PASS

*I. URL / dopasowanie* · entry about ANOTHER dispatch (same site, person and topic) · driven as `url_in_message` · 0.24 s

- Organisers' question: Czy ten wpis dotyczy tej samej depeszy PAP, którą sprawdzał Demagog? [URL wpisu]
- Sent: Czy ten wpis dotyczy tej samej depeszy PAP, którą sprawdzał Demagog? {url}
- Organisers' example answer: Jeśli zgadzają się tytuł, temat i data depeszy, bot wskazuje, że chodzi o ten sam materiał, i pokazuje podstawę dopasowania. Jeśli wpis dotyczy innej depeszy, podobny temat lub sama domena pap.pl nie wystarczą. Do testu najlepiej przygotować oba warianty.
- Publication it depends on: Demagog, “Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta” — in the corpus (demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela)

Reply (with the controlled page):

```
❔ *Brak wystarczających dowodów*
Nie udało mi się potwierdzić, że to ten materiał, który sprawdzali fact-checkerzy: nagłówka ze strony („Premier: rząd przygotowuje rozporządzenie o stanie klęski żywiołowej”) nie ma w żadnej analizie w katalogu źródeł. Podobny temat, ta sama osoba albo ta sama domena nie wystarczą do dopasowania.
Podstawa: niewystarczająca — nagłówek lub data strony nie zgadzają się z żadną analizą w katalogu źródeł.
Ograniczenie: przeszukano tylko katalog zaufanych źródeł — mogło w nim zabraknąć tej sprawy.

📨 Sprawa SPR-E2211B trafiła do kolejki analityka.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/0d9f1dd412b2
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Donald Tusk uspokajał przed powodzią. Depesza PAP nie został” — demagog.jsonl: demagog:wypowiedzi/donald-tusk-uspokajal-przed-powodzia-depesza-pap-nie-zniknela
- ✓ status is ok
- ✓ verdict is not falszywe / potwierdzone / wprowadzajace_w_blad
- ✓ the fact-check is NOT used as the decisive source
- ✓ reply: says it is not the same dispatch or that no match could be established
- ✓ reply never: states that it is the same dispatch / material
- ✓ the linked page was fetched
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 236 ms

### J1-api-dziala — PASS

*J. Awaria API* · working search, publication found · driven as `text` · 0.67 s

- Organisers' question: Czy Demagog sprawdzał, czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków?
- Sent: Czy Demagog sprawdzał, czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków?
- Organisers' example answer: [Przy działającym API i trafieniu: „Tak, Demagog to sprawdził i ocenił twierdzenie jako fałsz”, z linkiem do publikacji. Przy wymuszonej awarii: „Nie mogę teraz sprawdzić indeksu Google z powodu błędu dostępu”. Bot nie powinien mówić „nie ma takiego artykułu”. demagog]
- Publication it depends on: Demagog, “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy” — in the corpus (demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy)

Reply (main):

```
❌ *Fałszywe*
Tak, Demagog to sprawdził i ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że nie 70, tylko 65-latkowie we Wrocławiu, jeżdżą komunikacją miejską bezpłatnie” jako „Fałsz” (analiza z 12.03.2024). Demagog pisze: „Wrocław nie jest jedynym miastem oferującym osobom powyżej 65. roku życia darmową komunikację miejską. Z takiej ulgi korzystają również seniorzy i seniorki w Bydgoszczy, w Toruniu oraz w Lublinie”.
Źródło: Demagog, 12.03.2024 — Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy
https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: źródło sprawdzało bardzo podobne, a nie identyczne twierdzenie.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/1397181b7688
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawd” — demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy
- ✓ status is ok
- ✓ verdict is falszywe
- ✓ the answer opens with 'Tak'
- ✓ decisive source is the expected publication
- ✓ the reply links the expected publication
- ✓ the quote is verbatim in the corpus record
- ✓ the quote itself carries the finding
- ✓ reply: names Demagog as the checker
- ✓ reply: says Demagog checked it
- ✓ reply: says the claim was rated false
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 661 ms

### J2-awaria-api — PASS

*J. Awaria API* · forced failure of the live providers; publication is in the local corpus · driven as `forced_failure` · 0.6 s

- Organisers' question: Czy Demagog sprawdzał, czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków?
- Sent: Czy Demagog sprawdzał, czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków?
- Organisers' example answer: [Przy działającym API i trafieniu: „Tak, Demagog to sprawdził i ocenił twierdzenie jako fałsz”, z linkiem do publikacji. Przy wymuszonej awarii: „Nie mogę teraz sprawdzić indeksu Google z powodu błędu dostępu”. Bot nie powinien mówić „nie ma takiego artykułu”. demagog]
- Publication it depends on: Demagog, “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy” — in the corpus (demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy)

Reply (PRAWDOWID_FORCE_FAIL=google_factcheck,websearch):

```
❌ *Fałszywe*
Tak, Demagog to sprawdził i ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej to przede wszystkim doprowadzenie do tego, że nie 70, tylko 65-latkowie we Wrocławiu, jeżdżą komunikacją miejską bezpłatnie” jako „Fałsz” (analiza z 12.03.2024). Demagog pisze: „Wrocław nie jest jedynym miastem oferującym osobom powyżej 65. roku życia darmową komunikację miejską. Z takiej ulgi korzystają również seniorzy i seniorki w Bydgoszczy, w Toruniu oraz w Lublinie”.
Źródło: Demagog, 12.03.2024 — Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy
https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy/
Podstawa: umiarkowana — 1 źródło (fact-checking: Demagog).
Ograniczenie: wyszukiwanie na żywo (indeks Google lub zaufane strony) było niedostępne (błąd techniczny), więc wynik opiera się tylko na lokalnej bazie; poza tym źródło sprawdzało bardzo podobne, a nie identyczne twierdzenie.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/6fd8c5be2c53
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawd” — demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy
- ✓ status is ok or blad_techniczny
- ✓ verdict is falszywe or brak_dowodow
- ✓ reply: technical 'cannot check now' notice
- ✓ reply never: claims that no such article exists
- ✓ live stage ran and reported status 'blad'
- ✓ the failure is logged (errors table)
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 596 ms

### J3-awaria-bez-kopii-lokalnej — PASS

*J. Awaria API* · forced failure; the publication is hidden from the local index (the live index is the only way) · driven as `forced_failure` · 0.13 s

- Organisers' question: Czy Demagog sprawdzał, czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków?
- Sent: Czy Demagog sprawdzał, czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków?
- Organisers' example answer: [Przy działającym API i trafieniu: „Tak, Demagog to sprawdził i ocenił twierdzenie jako fałsz”, z linkiem do publikacji. Przy wymuszonej awarii: „Nie mogę teraz sprawdzić indeksu Google z powodu błędu dostępu”. Bot nie powinien mówić „nie ma takiego artykułu”. demagog]
- Publication it depends on: Demagog, “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy” — in the corpus (demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy)

Reply (PRAWDOWID_FORCE_FAIL=google_factcheck,websearch):

```
❔ *Brak wystarczających dowodów*
Nie udało mi się tego potwierdzić w lokalnej bazie, a wyszukiwanie na zaufanych stronach jest teraz niedostępne (błąd techniczny), więc nie wiem, czy coś tam jest. Znalazłem tylko materiał pokrewny — Demagog (05.04.2024): „Darmowa komunikacja. Jaką kwotę musiałby dołożyć Wrocław?”. Nie rozstrzyga on samego twierdzenia — w pełnej analizie sprawdzisz, czego dokładnie dotyczy. Brak wyniku w bazie nie oznacza, że to nieprawda.
Materiał pokrewny (nie rozstrzyga): Demagog, 05.04.2024 — Darmowa komunikacja. Jaką kwotę musiałby dołożyć Wrocław?
https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-jaka-kwote-musialby-dolozyc-wroclaw/
Podstawa: niewystarczająca — są tylko materiały na pokrewny temat.
Ograniczenie: wyszukiwanie na zaufanych stronach było niedostępne (błąd techniczny) — sprawdzono tylko lokalną bazę.

📨 Sprawa SPR-85ABB7 trafiła do kolejki analityka.

Pełna analiza i wszystkie źródła: http://localhost:8000/analiza/9f3d574272ac
(Odpowiedź automatyczna — zajrzyj do źródła.)
```

Checks:

- ✓ corpus contains Demagog “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawd” — demagog.jsonl: demagog:wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy
- ✓ harness: the hidden publication did not reach the answer — it is still among the evidence
- ✓ status is ok or blad_techniczny
- ✓ verdict is brak_dowodow
- ✓ no decisive source is presented
- ✓ reply: technical 'cannot check now' notice
- ✓ reply never: claims that no such article exists
- ✓ reply never: attaches a fact-check rating of some other claim to an abstention
- ✓ live stage ran and reported status 'blad'
- ✓ the failure is logged (errors table)
- ✓ every verdict rests on a source quoted verbatim from the corpus
- ✓ a case is mentioned only if the store really recorded this submission
- ✓ answered within 30 s — 117 ms

