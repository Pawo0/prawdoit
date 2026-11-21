# Uruchomienie w kontenerze

Obraz zawiera backend, stronę WWW, katalog źródeł i gotowy cache embeddingów. Nie wymaga GPU ani klucza do LLM.
Modele są pobierane przy pierwszym uruchomieniu do osobnego wolumenu. Obraz nie zawiera danych surowych,
lokalnej historii, środowiska `.venv`, testów przeglądarkowych ani sekretów.

## Lokalnie lub na VPS

Wymagania: Docker Engine z Compose v2, internet przy budowaniu i pierwszym starcie. Jako punkt startowy do
pilotażu przyjmij 4 vCPU, 8 GB RAM i co najmniej 10 GB wolnego dysku; to założenie, nie wynik testu obciążeniowego.
Czas pobrania modeli zależy od łącza. Pierwszy start może potrwać kilka minut, a przebudowanie indeksu po zmianie
korpusu znacznie dłużej.

W katalogu projektu:

```bash
cp .env.example .env
```

W `.env` ustaw `PRAWDOWID_MODERATOR_TOKEN` na własny losowy token. Możesz wygenerować go poleceniem
`openssl rand -hex 32`. Zachowaj go — służy do dostępu do panelu analityka. `.env` nie trafia do repozytorium ani obrazu.
Kontener nie uruchomi się z pustym tokenem lub domyślnym `demo-moderator`.

```bash
docker compose up -d --build
docker compose logs -f backend
```

Po komunikacie `Application startup complete` otwórz http://localhost:8000. Strona i API są dostępne pod tym samym
adresem. W `docker compose ps` backend powinien osiągnąć stan `healthy`. Odpowiedź z `/api/health` zawiera liczbę
dokumentów korpusu. Healthcheck czeka na pełne załadowanie modeli i nie uruchamia ich w dodatkowym procesie.
Okno startowe healthchecka wynosi 30 minut; przez ten czas kontener może mieć stan `starting`.

```bash
curl --fail http://localhost:8000/api/health
```

Serwer działa jako użytkownik UID/GID 10001, z jednym workerem. Kolejny worker oznacza kolejną kopię modeli
w pamięci; współdzielenie SQLite przez repliki nie jest obecnie obsługiwanym sposobem skalowania.

## Publiczny HTTPS z Caddy

Skieruj rekord DNS domeny na VPS i udostępnij porty TCP 80/443. Ustaw w `.env`:

```dotenv
PRAWDOWID_DOMAIN=prawdowid.example.com
PRAWDOWID_PUBLIC_URL=https://prawdowid.example.com
PRAWDOWID_TRUSTED_PROXY_IPS=*
```

Następnie:

```bash
docker compose --profile tls up -d --build
docker compose logs -f backend caddy
```

Caddy uzyskuje i odnawia certyfikat, a żądania kieruje do backendu po prywatnej sieci Compose. Nie zmieniaj
`PRAWDOWID_BIND_ADDRESS=127.0.0.1` przy konfiguracji `PRAWDOWID_TRUSTED_PROXY_IPS=*`: nagłówki adresu klienta
mogą wtedy pochodzić tylko z zaufanej ścieżki proxy. Przy istniejącym reverse proxy możesz pominąć profil `tls`
i kierować ruch do `127.0.0.1:8000`, ustawiając zaufane adresy proxy odpowiednio do swojej infrastruktury.

Panel moderatora używa tokenu z `.env`, a nie tokenu demonstracyjnego z instrukcji uruchamiania bez Dockera.
HTTPS jest potrzebny przed przesyłaniem rzeczywistych zgłoszeń i danych dostępowych przez internet.

## Limity zapytań i adres klienta za proxy

Limity są liczone na adres klienta, w oknie jednej minuty, w pamięci procesu (`backend/prawdowid/ratelimit.py`):

| Zmienna | Domyślnie | Czego dotyczy |
|---|---|---|
| `PRAWDOWID_RATE_LIMIT` | 120 | `POST /api/check` i `/api/check/async` (zestaw jury ma co najmniej 30 przypadków) |
| `PRAWDOWID_RATE_LIMIT_QUICK` | 60 | `POST /api/quick` — paczki wtyczki (do 40 fragmentów w paczce) |
| `PRAWDOWID_RATE_LIMIT_AUTO` | 20 | sprawdzenia w tle (`mode: "auto"`); liczą się też do pierwszego limitu |
| `PRAWDOWID_QUICK_CONCURRENCY` | 1 | ile paczek `/api/quick` liczy się naraz; pozostałe czekają do 3 s, potem 503 |

Przekroczenie limitu to odpowiedź 429 z nagłówkiem `Retry-After` (sekundy) — nigdy wynik merytoryczny.

**Za reverse proxy adresem połączenia jest proxy.** Bez dodatkowej konfiguracji wszyscy użytkownicy dzielą wtedy jeden
limit. uvicorn (uruchamiany z domyślnym `--proxy-headers`) podstawia adres z nagłówka `X-Forwarded-For` tylko wtedy,
gdy połączenie przychodzi z adresu wymienionego w `FORWARDED_ALLOW_IPS` (domyślnie `127.0.0.1,::1`). W Compose tę
zmienną ustawia `PRAWDOWID_TRUSTED_PROXY_IPS`:

- profil `tls` (Caddy w sieci Compose): `PRAWDOWID_TRUSTED_PROXY_IPS=*` — jak wyżej; port backendu musi wtedy
  pozostać na `127.0.0.1`, bo inaczej każdy mógłby podać dowolny adres w nagłówku;
- własne proxy na tym samym hoście przed kontenerem: połączenie przychodzi z bramy sieci Dockera, nie z `127.0.0.1` —
  podaj jej adres lub podsieć, np. `PRAWDOWID_TRUSTED_PROXY_IPS=172.16.0.0/12`;
- uruchomienie bez Dockera za tunelem lub proxy na tym samym hoście (np. `cloudflared`): domyślne `127.0.0.1` wystarcza,
  o ile tunel dodaje `X-Forwarded-For`; w innym układzie ustaw `FORWARDED_ALLOW_IPS` lub `--forwarded-allow-ips`.

Sprawdzenie: `backend/.venv/bin/python backend/tests/test_rate_limit.py` (klasa `ProxyAddress` używa tego samego
middleware, które instaluje uvicorn). Limity są lokalne dla procesu — druga replika wymaga wspólnego magazynu.

## Hosting przyjmujący własny obraz Docker

Zbuduj i wypchnij obraz do własnego rejestru:

```bash
docker build -t REGISTRY/TEAM/prawdowid:VERSION .
docker push REGISTRY/TEAM/prawdowid:VERSION
```

To polecenie buduje obraz dla architektury hosta. Na Apple Silicon jest to ARM64. Dla serwera AMD64 użyj
`docker buildx build --platform linux/amd64 -t REGISTRY/TEAM/prawdowid:VERSION --push .` na maszynie
z obsługą tej architektury lub emulacji.

Ustaw zmienne `PRAWDOWID_MODERATOR_TOKEN` i `PRAWDOWID_PUBLIC_URL`. Proces nasłuchuje na `0.0.0.0`,
obsługuje zmienną `PORT` narzuconą przez platformę (domyślnie 8000) i przejmuje sygnały zatrzymania bez powłoki pośredniej.
Zapewnij trwały, zapisywalny dysk pod `/var/lib/prawdowid` oraz opcjonalnie cache pod `/var/cache/huggingface`,
dostępny dla UID/GID 10001. Backend potrzebuje dostępu do stron źródłowych przy sprawdzaniu URL i do Hugging Face
przy pierwszym pobieraniu modeli. Nie wymaga dostępu do Dockera z wnętrza kontenera.

Dysk efemeryczny oznacza utratę historii przy wymianie instancji i ponowne pobieranie modeli. Przy tej wersji aplikacji
wybierz pojedynczą instancję z trwałym dyskiem, zamiast wielu replik lub funkcji serverless.

## Dane, aktualizacje i kopie zapasowe

Compose tworzy wolumeny:

- `state`: SQLite z historią i sprawami moderatora oraz aktualizowany cache indeksu;
- `models`: pobrane modele Hugging Face;
- `caddy_data` / `caddy_config`: certyfikaty i konfiguracja Caddy, jeżeli używasz TLS.

Nazwy w silniku mają dodatkowo prefiks projektu Compose. `docker compose down` pozostawia wolumeny.
**`docker compose down -v` usuwa je wraz z historią i modelami.**

Po zmianie kodu lub korpusu:

```bash
docker compose up -d --build
```

Dla TLS dodaj `--profile tls`. Korpus jest częścią obrazu. Kontener kopiuje gotowe embeddingi tylko do pustego cache,
a aplikacja uzupełnia go dla nowych fragmentów. Nie nadpisuje istniejącej bazy SQLite. Wykonuj kopie wolumenu
`state` przy zatrzymanym backendzie, aby otrzymać spójną kopię bazy. Przywracaj z zachowaniem właściciela UID 10001.

Po pierwszym udanym pobraniu modeli możesz ustawić `HF_HUB_OFFLINE=1`, aby ładować je wyłącznie z wolumenu.
To blokuje pobieranie modeli, nie pobieranie stron URL. Zmiana modelu wymaga wcześniejszego wypełnienia cache.

Bez Compose obraz można uruchomić tak:

```bash
docker run -d --name prawdowid \
  --env-file .env \
  -p 127.0.0.1:8000:8000 \
  -v prawdowid-state:/var/lib/prawdowid \
  -v prawdowid-models:/var/cache/huggingface \
  prawdowid:local
```

## Wtyczka

Po wdrożeniu zmień adres serwera w ustawieniach wtyczki na publiczny adres HTTPS i wyłącz tryb demonstracyjny.
Przy domenie innej niż dotychczas obsługiwane adresy sprawdź również `host_permissions` w
`extension/manifest.json` i dodaj konkretny adres, np. `https://prawdowid.example.com/*`, jeżeli przeglądarka
nie zezwala na żądania do nowego serwera. Następnie przeładuj rozszerzenie i testowane karty.

## Zależności

`backend/requirements-container.txt` przypina bezpośrednie zależności runtime do wersji z lokalnego środowiska
Python 3.12. Zależności pośrednie są rozwiązywane podczas budowania — nie jest to pełny lockfile.
PyTorch jest instalowany z oficjalnego indeksu CPU; Playwright, Discord i MCP nie są potrzebne do uruchomienia API.
Fonty i grafiki strony są częścią obrazu, bez zależności od CDN.

## Sprawdzenie wdrożenia

Po uruchomieniu kontenera wykonaj `python3 eval/test_container.py --base http://localhost:8000`.
Test sprawdza korpus, stronę, font, rzeczywiste zapytanie do silnika oraz odczyt wyniku z SQLite.
Usuwa utworzoną przez siebie sesję. Test inicjalizacji cache i ochrony tokenu: `python3 eval/test_container_start.py`.

Walidacja wykonana podczas przygotowania: zbudowany obraz Linux/ARM64 w Podmanie (lokalny odpowiednik polecenia
Docker), uruchomienie z cache modeli i `HF_HUB_OFFLINE=1`, rzeczywista inferencja na korpusie 2285 dokumentów,
healthcheck, odczyt SQLite po zastąpieniu kontenera przez instancję Compose, nieuprzywilejowany użytkownik
oraz walidacja konfiguracji Caddy. Pobieranie modeli od zera i publiczne wydanie certyfikatu wymagają internetu
oraz własnej domeny; ten test korzystał z wcześniej pobranego cache i nie wdrażał aplikacji publicznie.
