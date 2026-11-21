# Prawdowid — koszty, zależności zewnętrzne i zachowanie pod obciążeniem

## Pomiar (prototyp)
Laptop i5-8365U (4 rdzenie, bez GPU), obciążony innymi procesami (load average 10–20):
- pełne sprawdzenie tekstu (`/api/check`): **mediana 0,5–1,5 s, p95 < 5 s** (zbiory `eval/`), ≈ 1–2 CPU-s na zapytanie;
- szybka ścieżka wtyczki (`/api/quick`): 9 postów w paczce ≈ 3–12 s na obciążonym laptopie (embedding + NLI tylko dla kandydatów); wyniki cache'owane po haszu tekstu;
- start serwera z gotowym indeksem: ~10 s; pierwsze zbudowanie indeksu embeddingów dla ~11 tys. fragmentów: ~20 min na tym CPU (jednorazowo, potem przyrostowo).

**Wyszukiwanie na żywo** uruchamia się tylko wtedy, gdy baza nie dała dowodu (w zbiorach `eval/` 32–35% przypadków).
Wtedy czas odpowiedzi rośnie do ok. 6–15 s (budżet 15 s), a koszt obliczeń praktycznie się nie zmienia (czekanie na sieć).
Każde sprawdzenie zapisuje szacunek kosztu (`engine.cost_estimate`: czas × stawka CPU + tokeny LLM × stawka; stawki
`PRAWDOWID_COST_PLN_PER_CPU_S`, `PRAWDOWID_COST_PLN_PER_1K_LLM_TOKENS`), suma i mediana są w `/api/stats`.

## Koszt 1 000 zapytań
| Składnik | Koszt | Uwagi |
|---|---|---|
| Obliczenia (własny serwer CPU w EOG) | ≈ 0,5 CPU-h → **< 0,05 zł** krańcowo | mały VPS 4 vCPU / 8 GB w UE (rząd wielkości 60–120 zł/mies.) obsłuży kilkadziesiąt tys. sprawdzeń dziennie |
| Modele (embedding, NLI) | **0 zł** | otwarte licencje (Apache-2.0 / MIT), działają lokalnie, brak kluczy API |
| Opcjonalny LLM (upraszczanie języka) | 0 zł lokalnie (Bielik/PLLuM, wymaga mocniejszego serwera/GPU) albo ≈ 2 mln tokenów / 1000 zapytań w API UE (np. Mistral) → rząd wielkości **1–2 zł** | domyślnie wyłączony; brak klucza/limit → wyjaśnienie z szablonu (nie wpływa na werdykt) |
| Wyszukiwanie na żywo (wyszukiwarki serwisów, Google Fact Check API) | **0 zł** | darmowe w limitach; opcjonalny Brave — wg cennika dostawcy (kilkaset zapytań na 1 000 sprawdzeń) |
| Kanał WWW / PWA / wtyczka | 0 zł | — |
| Discord, Messenger | 0 zł | Messenger wymaga App Review do publicznego użycia |
| WhatsApp Cloud API | **0 zł** w limicie 1 000 wiadomości serwisowych/mies. na numer; dalej ok. 0,0122 USD/wiad. (PL, wg kopii cennika Meta — do potwierdzenia) | instytucje publiczne mogą kwalifikować się do zwolnienia; numer telefonu (SIM) |
| SMS (np. SMSAPI) | **ok. 170–340 zł** / 1 000 odpowiedzi (1–2 segmenty bez polskich znaków) + numer przychodzący 99–149 zł/mies. | standardowe opłaty operatora po stronie użytkownika — należy je jasno komunikować |

**Utrzymanie kanału demonstracyjnego:** 0 zł (adapter demo + Discord). Dostęp dla użytkownika jest bezpłatny po stronie usługi.

## Zależności zewnętrzne i zachowanie przy awarii
| Zależność | Wymagany klucz | Co, jeśli brak/limit/awaria |
|---|---|---|
| Hugging Face (pobranie modeli przy pierwszej instalacji) | nie | po pobraniu działa offline (`HF_HUB_OFFLINE=1`) |
| Strony źródłowe (ingest) | nie | korpus działa z ostatniej kopii; `retrieved_at` pokazuje datę pobrania |
| Strona z URL podanego przez użytkownika | nie | status „Błąd techniczny — to nie jest ocena treści” + prośba o wklejenie tekstu |
| WhatsApp/Messenger Graph API | tak (`PRAWDOWID_WA_*`, `PRAWDOWID_FB_*`) | bez kluczy: adapter demo; błąd wysyłki logowany, nie udajemy doręczenia |
| Opcjonalny LLM | zależnie od dostawcy | wyjaśnienie z szablonu; w audycie `llm_calls.used=false` |
| Wyszukiwarki zaufanych serwisów (gov.pl, WordPress REST: Demagog, FakeNews.pl, CheckFirst) | nie | publiczne funkcje wyszukiwania operatorów, 0 zł; robots.txt sprawdzany; 7 s na serwis — timeout/awaria → komunikat, odpowiedź z bazy |
| Google Fact Check Tools API | tak (`PRAWDOWID_GOOGLE_FACTCHECK_KEY`) | bezpłatne, limit wg przydziału projektu w Google Cloud; bez klucza nieaktywne; błąd/limit → „Nie mogę teraz sprawdzić indeksu Google…”; zapytanie (tekst twierdzenia) trafia do Google (USA) |
| SearXNG (opcjonalnie, `PRAWDOWID_SEARXNG_URL`) | nie | własna instancja (np. VPS w UE, rząd wielkości 20–40 zł/mies.); awaria → komunikat |
| Brave Search API (opcjonalnie, `PRAWDOWID_BRAVE_KEY`) | tak | płatne wg cennika Brave (pakiet darmowy + opłata za 1 000 zapytań — sprawdzić aktualny cennik); dostawca spoza EOG |
| EUvsDisinfo MCP (`PRAWDOWID_EUVSDISINFO_TOKEN`) | tak (od organizatora) | pobierane w tle przez harmonogram, nie w ścieżce zapytania; brak tokenu → status źródła „błąd”, korpus z ostatniej kopii |

## Pod obciążeniem
- API jest bezstanowe (poza SQLite audytu) → skalowanie poziome (kilka workerów uvicorn/gunicorn za load balancerem); SQLite → PostgreSQL przy wielu instancjach.
- Limity na adres klienta i minutę: 120 pełnych sprawdzeń, 60 paczek wtyczki (`/api/quick`), 20 sprawdzeń w tle; osobny limit per użytkownik kanału; Meta wymaga szybkiej odpowiedzi 200 na webhook — przetwarzanie odbywa się w tle.
- Wtyczka: paczki ≤ 16 fragmentów, cache po stronie klienta i serwera (popularne posty powtarzają się → wysoki współczynnik trafień), skanowanie tylko widocznych elementów.
- Wąskie gardło: NLI na CPU. Przy większym ruchu: GPU lub model NLI w ONNX/int8 (≈ 3× szybciej), osobny worker dla `/api/quick`.

## Gdzie przetwarzane są dane
Domyślnie wszystko na serwerze zespołu/MSZ (modele lokalne). Wyszukiwanie na żywo wysyła **słowa kluczowe** twierdzenia
(nie całe wejście, nie dane użytkownika) do wyszukiwarek zaufanych serwisów, a z kluczem Google — tekst twierdzenia do
Google Fact Check API (USA); `PRAWDOWID_LIVE_SEARCH=0` wyłącza ten przepływ. Kanały Meta (WhatsApp/Messenger) przetwarzają treść wiadomości również na infrastrukturze Meta (także poza EOG) — użytkownik jest o tym informowany; strona WWW, wtyczka i Discord-demo nie wymagają Meta.
