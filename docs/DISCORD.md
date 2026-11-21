# Discord — konfiguracja i uruchomienie

Bot działa jako cienki adapter tego samego silnika, którego używają WWW i ręczne sprawdzanie we wtyczce.
Nie wymaga osobnego modelu ani klucza do LLM. Obsługuje tekst i samodzielny publiczny URL, po polsku.
Każde zgłoszenie jest niezależne: bot nie korzysta z historii rozmowy do interpretowania kolejnego pytania.

## 1. Discord Developer Portal

1. Otwórz https://discord.com/developers/applications i wybierz **New Application** → `Prawdowid`.
2. W **Bot** wygeneruj token i włącz **Message Content Intent**. Inne uprzywilejowane intencje nie są potrzebne.
3. W **Installation** wybierz **Guild Install**, **Discord Provided Link**, zakresy `bot` i `applications.commands`.
4. Przyznaj **View Channels**, **Send Messages**, **Read Message History**; dla wątków dodatkowo
   **Send Messages in Threads**. Bot nie wymaga uprawnienia Administrator.
5. Otwórz link instalacyjny i dodaj bota na serwer testowy. Sprawdź nadpisania uprawnień kanału.

Bot korzysta z połączenia wychodzącego Gateway; nie ustawiaj Interactions Endpoint URL. Nie potrzeba tunelu
ani publicznego webhooka. Proces musi mieć dostęp do Discorda i lokalnego API. Wymagania Discorda dotyczące
weryfikacji aplikacji i uprzywilejowanych intencji należy sprawdzić przed rozszerzeniem liczby serwerów.

## 2. Docker Compose — backend i bot razem

W katalogu projektu skopiuj `.env.example` do `.env`, jeśli jeszcze go nie masz. Zachowaj istniejący plik.
Ustaw prywatny token moderatora i token bota:

```dotenv
PRAWDOWID_MODERATOR_TOKEN=TU_WLASNY_LOSOWY_TOKEN
PRAWDOWID_DISCORD_TOKEN=TU_TOKEN_Z_DISCORDA
PRAWDOWID_DISCORD_SESSION_SECRET=TU_STALY_LOSOWY_SEKRET
PRAWDOWID_DISCORD_RATE_LIMIT=5
PRAWDOWID_PUBLIC_URL=http://localhost:8000
```

Sekret sesji wygeneruj np. `openssl rand -hex 32`. Przechowuj go stabilnie: zmiana sekretu powoduje, że bot
nie potrafi już wskazać starych sesji do usunięcia. Gdy sekret jest pusty, jego rolę pełni token bota,
więc zmiana tokenu ma ten sam skutek. Stary prototyp używał niesekretnego SHA-256 ID użytkownika; nowe sesje
używają HMAC i nie są połączone ze starymi. Stare dane wygasają według retencji lub wymagają usunięcia
przez administratora.

```bash
docker compose up -d --build
docker compose logs -f backend
```

Ten sam kontener uruchamia API, czeka na jego gotowość, a następnie uruchamia bota. Modele są ładowane
wyłącznie przez API. Oczekiwany komunikat to `Prawdowid bot online as ...`. Bez tokenu Discorda działa
samo API. Awaria procesu bota powoduje ponowienie po 30 sekundach, bez przeładowywania modeli API.
Zatrzymanie kontenera zatrzymuje oba procesy. Awaria API kończy kontener, aby polityka restartu odtworzyła usługę.
Nie uruchamiaj drugiej kopii bota z tym samym tokenem i katalogiem stanu.

Obraz uruchomiony przez `docker run --env-file .env ...` zachowuje się tak samo. Tokeny są wczytywane
z otoczenia w czasie startu, nie są kopiowane do obrazu ani zapisywane w logach aplikacji.

`PRAWDOWID_PUBLIC_URL` jest adresem strony otwieranej przez użytkownika, a nie adresem połączenia bota z API.
Na własnym komputerze może to być `http://localhost:8000`. Dla jury lub innych użytkowników ustaw publiczny
adres HTTPS i skonfiguruj hosting według `DEPLOYMENT.md`. Samo ustawienie zmiennej nie publikuje strony.

## 3. Sposoby użycia

- DM: `Czy to prawda, że Ukraina nie płaci Orlenowi za paliwo?`
- Kanał: `@Prawdowid Czy to prawda, że Ukraina nie płaci Orlenowi za paliwo?`
- Komenda: `/sprawdz tekst:Ukraina w ogóle nie płaci Orlenowi za paliwo`.
- Menu wiadomości: **Aplikacje → Sprawdź w Prawdowidzie** (odpowiedź prywatna).
- Usunięcie własnych sprawdzeń: `/usun_sesje` (odpowiedź prywatna); w DM działa też tekst `usuń sesję`.

Komenda `/sprawdz` i odpowiedzi na oznaczenie na kanale są publiczne dla osób widzących kanał.
Załączniki nie są pobierane: bot jawnie informuje o braku OCR/analizy nagrań. Jeżeli wiadomość ma tekst
oraz załącznik, sprawdzany jest tylko tekst. Brak treści skutkuje instrukcją użycia.
Długie wyniki są dzielone na wiadomości, bez obcinania końca analizy. Automatyczne oznaczanie użytkowników,
ról i `@everyone` jest wyłączone w odpowiedziach, także gdy takie ciągi pojawią się w analizowanym tekście.

## 4. Limity, dane i błędy

Domyślnie: 5 operacji na użytkownika na minutę, jedno aktywne sprawdzenie/usunięcie na użytkownika,
maksymalnie 2 aktywne operacje bota łącznie. API dodatkowo współdzieli limit `PRAWDOWID_RATE_LIMIT`
(30/min/IP) między `/api/check` i `/api/chat-reply`; wszystkie zgłoszenia tego bota pochodzą z jednego IP.
Wiadomości powyżej 6000 znaków są odrzucane, a nie obcinane. Timeout API wynosi 45 s.
Limit, awaria lub błędna odpowiedź API są komunikowane osobno od werdyktu.

ID Discorda jest zamieniane na sekretowy pseudonim HMAC. Surowe ID nie trafia do API.
`/usun_sesje` usuwa sprawdzenia, powiązane zdarzenia bezpieczeństwa, błędy i feedback; usuwa osierocone
sprawy moderatora i odwołania do sprawdzeń we współdzielonych sprawach. Wspólna sprawa może pozostać,
jeśli zawiera zgłoszenia innych użytkowników (w tym jej zagregowany wektor podobieństwa i notatka analityka).
Komenda nie usuwa wiadomości ani odpowiedzi przechowywanych przez Discorda. Retencja API jest konfigurowana
przez `PRAWDOWID_RETENTION_DAYS`; czyszczenie przeterminowanych rekordów następuje przy starcie backendu.
Treść wiadomości przechodzi również przez infrastrukturę Discorda; lokalne modele nie eliminują tej zależności.

## 5. Opcjonalne alerty moderatorów

Włącz tryb deweloperski w Discordzie i skopiuj ID **prywatnego kanału moderatorów**, na którym bot może pisać.
W `.env` ustaw:

```dotenv
PRAWDOWID_DISCORD_ALERT_CHANNEL_ID=123456789012345678
```

Następnie odtwórz kontener: `docker compose up -d`.
Puste ID oznacza brak wysyłania alertów. Bot co 60 s pobiera przez autoryzowane API sprawy ze wszystkich
kanałów i powiadamia o otwartych sprawach z priorytetem wysokim (tematy wysokiego ryzyka lub ≥3 podobne
zgłoszenia). Pierwsze włączenie obejmie też istniejące otwarte sprawy. Alert zawiera tylko ID sprawy,
liczbę zgłoszeń i link do panelu; nie wysyła treści pytania, tokenu moderatora ani ID pytającego.
Panel nadal wymaga podania tokenu moderatora.

Potwierdzone wysyłki zapisywane są w wolumenie `state` jako `runtime/discord-alerts.json`. Bez nowego
zgłoszenia bot nie wysyła tego samego alertu ponownie po restarcie. Błąd doręczenia jest logowany i ponawiany;
nie jest przedstawiany jako udane powiadomienie. Awaria pomiędzy wysłaniem i zapisem potwierdzenia może
spowodować powtórny alert. Powiadomienie nie oznacza rozpatrzenia sprawy przez człowieka.

## 6. Sprawdzenie

```bash
backend/.venv/bin/python eval/test_discord.py
python3 eval/test_container_start.py
```

Testy lokalne wykorzystują kontrolowane odpowiedzi HTTP i Discorda; nie potrzebują tokenu ani modeli.
Test na prawdziwym Discordzie: DM, oznaczenie, komenda, menu wiadomości, obraz bez tekstu, długi wynik,
usunięcie sesji i zgodność werdyktu/źródeł dla tego samego pytania w WWW. Wyłącz API, aby sprawdzić
komunikat techniczny. Do alertów ustaw prywatny kanał i sprawdź nowe oraz powtórzone zgłoszenia.
