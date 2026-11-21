# Prawdowid — koszty, zależności zewnętrzne i zachowanie pod obciążeniem

## Pomiar (prototyp)
Laptop i5-8365U (4 rdzenie, bez GPU), obciążony innymi procesami (load average 10–20):
- pełne sprawdzenie tekstu (`/api/check`): **mediana 0,5–1,5 s, p95 < 5 s** (zbiory `eval/`), ≈ 1–2 CPU-s na zapytanie;
- szybka ścieżka wtyczki (`/api/quick`): 9 postów w paczce ≈ 3–12 s na obciążonym laptopie (embedding + NLI tylko dla kandydatów); wyniki cache'owane po haszu tekstu;
- start serwera z gotowym indeksem: ~10 s; pierwsze zbudowanie indeksu embeddingów dla ~11 tys. fragmentów: ~20 min na tym CPU (jednorazowo, potem przyrostowo).

## Koszt 1 000 zapytań
| Składnik | Koszt | Uwagi |
|---|---|---|
| Obliczenia (własny serwer CPU w EOG) | ≈ 0,5 CPU-h → **< 0,05 zł** krańcowo | mały VPS 4 vCPU / 8 GB w UE (rząd wielkości 60–120 zł/mies.) obsłuży kilkadziesiąt tys. sprawdzeń dziennie |
| Modele (embedding, NLI) | **0 zł** | otwarte licencje (Apache-2.0 / MIT), działają lokalnie, brak kluczy API |
| Opcjonalny LLM (upraszczanie języka) | 0 zł lokalnie (Bielik/PLLuM, wymaga mocniejszego serwera/GPU) albo ≈ 2 mln tokenów / 1000 zapytań w API UE (np. Mistral) → rząd wielkości **1–2 zł** | domyślnie wyłączony; brak klucza/limit → wyjaśnienie z szablonu (nie wpływa na werdykt) |
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

## Pod obciążeniem
- API jest bezstanowe (poza SQLite audytu) → skalowanie poziome (kilka workerów uvicorn/gunicorn za load balancerem); SQLite → PostgreSQL przy wielu instancjach.
- Limity: 30 zapytań/min/IP (WWW) i per użytkownik kanału; Meta wymaga szybkiej odpowiedzi 200 na webhook — przetwarzanie odbywa się w tle.
- Wtyczka: paczki ≤ 16 fragmentów, cache po stronie klienta i serwera (popularne posty powtarzają się → wysoki współczynnik trafień), skanowanie tylko widocznych elementów.
- Wąskie gardło: NLI na CPU. Przy większym ruchu: GPU lub model NLI w ONNX/int8 (≈ 3× szybciej), osobny worker dla `/api/quick`.

## Gdzie przetwarzane są dane
Domyślnie wszystko na serwerze zespołu/MSZ (modele lokalne). Kanały Meta (WhatsApp/Messenger) przetwarzają treść wiadomości również na infrastrukturze Meta (także poza EOG) — użytkownik jest o tym informowany; strona WWW, wtyczka i Discord-demo nie wymagają Meta.
