# API i kanały

API jest cienką warstwą nad usługą sprawdzania, rejestrem i magazynem danych. Dokładne schematy i odpowiedzi walidacji są dostępne pod `/docs` oraz `/openapi.json` po uruchomieniu serwera. Poniższy przewodnik wyjaśnia role endpointów i zasady integracji.

## Podstawowe modele

[`schemas.py`](../../backend/prawdowid/schemas.py) definiuje wspólne słownictwo:

- `CheckRequest`: `text`, `url`, opcjonalny `image_b64`, `channel`, `session`, `mode` i `live_search`.
- `CheckResult`: status wykonania, twierdzenia, podsumowanie, ostrzeżenia, sprawa, czasy i informacje o silniku.
- `ClaimResult`: werdykt jednego twierdzenia, dowody, przesłanki i ograniczenia.
- `Evidence`: tytuł, wydawca, daty, URL, fragment, relacja do tezy i metadane dopasowania.
- `QuickRequest` i `QuickResult`: paczka tekstów oraz wynik szybkiego routera wtyczki.
- `ChatRequest`: żądanie cienkiego adaptera czatu.

Schemat tekstu `CheckRequest` dopuszcza do 20000 znaków, ale usługa analizuje najwyżej `settings.max_input_chars`, domyślnie 6000. Klient powinien ograniczać tekst do 6000 znaków. `ChatRequest` waliduje limit 6000 bezpośrednio. Router przyjmuje najwyżej 40 fragmentów po 4000 znaków. Obraz podlega zarówno limitowi pola base64, jak i limitom rozmiaru oraz liczby pikseli w `ocr.py`.

## Status wykonania a werdykt

`status` opisuje wykonanie: `ok`, `blad_techniczny`, `doprecyzuj`, `poza_zakresem`.

`claims[].verdict` opisuje ustalenie: `potwierdzone`, `falszywe`, `wprowadzajace_w_blad`, `brak_dowodow`, `nie_podlega_weryfikacji`.

Nie należy zamieniać HTTP 429, HTTP 503, timeoutu ani statusu technicznego na informację, że wiadomość jest fałszywa lub nie ma dowodów. Wynik może jednocześnie zawierać ocenę opartą na lokalnym źródle i ostrzeżenie, że nie udało się sprawdzić zewnętrznego indeksu.

## Sprawdzenia i historia użytkownika

Główne endpointy znajdują się w [`api.py`](../../backend/prawdowid/api.py):

- `POST /api/check`: pełne synchroniczne sprawdzenie.
- `GET /api/check/{check_id}`: odczyt zapisanego wyniku; brak lub wygaśnięcie oznacza 404.
- `POST /api/chat-reply`: wspólna weryfikacja i tekst do wysłania przez adapter.
- `POST /api/quick`: szybkie dopasowanie każdego elementu paczki; `state` to `none`, `candidate` lub `match`.
- `DELETE /api/session/{session}`: usunięcie zapisów powiązanych z podanym identyfikatorem sesji.
- `POST /api/feedback`: zapis uwagi do sprawdzenia.
- `GET /api/health`: gotowość i informacje o silniku/korpusie.
- `GET /api/sources`: rejestr oraz podsumowanie wydawców i dokumentów.
- `GET /api/stats`: statystyki procesu sprawdzania i korpusu.

Identyfikator sesji jest kluczem pozwalającym wskazać dane do usunięcia, nie kontem użytkownika. Klient powinien generować go w sposób trudny do odgadnięcia i nie udostępniać innym osobom. Odczyt analizy jest publiczny dla posiadacza jej identyfikatora.

Przykład lokalnego sprawdzenia:

```bash
curl -X POST http://localhost:8000/api/check \
  -H 'Content-Type: application/json' \
  -d '{"text":"Wklej tutaj konkretne twierdzenie do sprawdzenia.","channel":"web","session":"losowy-identyfikator"}'
```

## Sprawdzenia asynchroniczne

[`jobs.py`](../../backend/prawdowid/jobs.py) obsługuje `POST /api/check/async`, które zwraca `job_id`, oraz `GET /api/jobs/{job_id}`, które raportuje stan, etap, upływ czasu i ostateczny wynik.

Zadania są pamięcią procesu, nie trwałą kolejką. Restart usuwa oczekujące zadania i ich uchwyty. Wykonane pełne sprawdzenie nadal ma osobny zapis audytu. Zadania mają TTL i limity współbieżności, a bierne sprawdzenia wtyczki osobną pojemność. Zakończony wynik biernego zadania jest usuwany z pamięci po odczycie.

## Autoryzacja paneli

Endpointy moderatora wymagają `X-Moderator-Token`, a rejestru `X-Admin-Token`. Wartości pochodzą z konfiguracji środowiska. Brak skonfigurowanego tokenu zamyka panel; jawne wartości demonstracyjne istnieją wyłącznie w trybie lokalnym `PRAWDOWID_DEV_MODE=1`.

`X-Admin-User` jest opisem autora zmiany w dzienniku, a nie osobnym mechanizmem uwierzytelnienia. Nie zastępuje tokenu administratora.

Moderator w `api.py`:

- `GET /api/cases`: sprawy, zdarzenia bezpieczeństwa, feedback i statystyki.
- `POST /api/cases/{case_id}`: status i notatka sprawy.
- `GET /api/export/checks.csv` lub `.json`: eksport przebiegu sprawdzeń. SQL jest w `store.export_checks()`.

Administrator w [`admin_api.py`](../../backend/prawdowid/admin_api.py):

- `GET /api/admin/sources` oraz `GET /api/admin/sources/{source_id}`: konfiguracja i stan źródeł.
- `POST /api/admin/sources`, `PUT` i `DELETE /api/admin/sources/{source_id}`: tworzenie, edycja i usunięcie.
- `POST /api/admin/sources/{source_id}/enable` lub `/disable`: zmiana kwalifikacji.
- `POST /api/admin/test` albo `/sources/{source_id}/test`: pobranie próbki bez zapisu korpusu.
- `POST /api/admin/sources/{source_id}/run`: uruchomienie pobierania.
- `POST /api/admin/suggest`: wykrycie konfiguracji na podstawie URL.
- `POST /api/admin/reload`: przeładowanie indeksu.
- `GET /api/admin/runs` i `/changes`: historia pobrań i konfiguracji.

W ostatniej grupie skróty zaczynające się od `/sources` odnoszą się do prefiksu `/api/admin`.

## Limity

Middleware dzieli budżety pełnych sprawdzeń i szybkich paczek. Dla `mode="auto"` jest dodatkowy limit. Odpowiedzi o przekroczeniu limitu lub braku wolnego slotu mogą zawierać `Retry-After`.

Adres klienta jest poprawny tylko przy właściwej konfiguracji zaufanego proxy. Ustawienia i domyślne wartości są w [`config.py`](../../backend/prawdowid/config.py), a konfiguracja proxy w [instrukcji wdrożenia](../DEPLOYMENT.md). Liczniki i kolejki są lokalne dla procesu; wielu workerów nie tworzy automatycznie jednego globalnego limitu.

## Kanały

[`channels/meta.py`](../../backend/prawdowid/channels/meta.py) tłumaczy webhooki WhatsApp/Messenger na wspólne sprawdzenie i tekst odpowiedzi. Wariant demonstracyjny pozwala przetestować kształt transportu bez konta dostawcy. Nie należy wystawiać go jako niekontrolowanej publicznej kolejki wiadomości.

Bot [`bots/discord_bot.py`](../../bots/discord_bot.py) działa poza pakietem backendu. Wywołuje `/api/chat-reply`, zarządza transportem, limitami użytkownika i powiadomieniami. Jego konfigurację opisuje [DISCORD.md](../DISCORD.md).

[`channels/formatting.py`](../../backend/prawdowid/channels/formatting.py) renderuje wynik. Adapter ma zachować werdykt, źródła i ograniczenia; formatowanie markdown i podział na wiadomości nie mogą zmieniać ustaleń.

## Strony i PWA

`api.py` serwuje WWW, zapisane analizy, pliki statyczne, manifest i service worker. `POST /share-target` obsługuje udostępnianie do PWA i przekierowuje do analizy. To warstwa dostarczania interfejsu, nie dodatkowy silnik weryfikacji.
