# Przewodnik po backendzie Prawdowida

Backend przyjmuje wiadomość, link lub zrzut ekranu, wyszukuje dowody i zwraca ocenę wraz z cytatami oraz ograniczeniami. Ten przewodnik jest przeznaczony dla osoby, która chce zrozumieć kod, uruchomić testy albo bezpiecznie zmienić jedną część systemu.

Najważniejsze rozróżnienie: `service.py` prowadzi całe sprawdzenie, `engine.py` ocenia pojedyncze twierdzenie, a adaptery HTTP i kanałów zajmują się transportem. Model NLI ocenia relację tekstów, natomiast końcowy werdykt powstaje z uporządkowanych reguł.

## Od czego zacząć

1. Przeczytaj [przebieg sprawdzenia](REQUEST_FLOW.md), a następnie `run_check()` w [`service.py`](../../backend/prawdowid/service.py). Funkcja pokazuje kolejne etapy bez zagłębiania się od razu w szczegóły sieci i modeli.
2. Zobacz [silnik weryfikacji](ENGINE.md), jeżeli interesuje Cię, skąd bierze się werdykt, cytat albo abstynencja.
3. Przejdź do [źródeł i wyszukiwania](SOURCES.md), jeżeli chcesz dodać źródło lub zrozumieć aktualizację korpusu.
4. Użyj [API i kanałów](API.md) do integracji z interfejsem lub botem.
5. Przed zmianą kodu przeczytaj [rozwój i testowanie](DEVELOPMENT.md).

[Mapa wszystkich modułów](MODULES.md) pomaga znaleźć konkretny plik. Zawiera odpowiedzialność każdego modułu oraz publiczne klasy i funkcje odczytane z jego kodu.

## Gdzie zmienić konkretną rzecz

- Nowy endpoint lub kod błędu HTTP: [`api.py`](../../backend/prawdowid/api.py), [`jobs.py`](../../backend/prawdowid/jobs.py) albo [`admin_api.py`](../../backend/prawdowid/admin_api.py).
- Pola wejścia i odpowiedzi: [`schemas.py`](../../backend/prawdowid/schemas.py).
- Podział wiadomości na twierdzenia: [`claims.py`](../../backend/prawdowid/claims.py), metadane i autorzy: [`linefilter.py`](../../backend/prawdowid/linefilter.py).
- Dopasowanie do sprawdzonej wcześniej wypowiedzi: [`engine.py`](../../backend/prawdowid/engine.py) i [`agreement.py`](../../backend/prawdowid/agreement.py).
- Liczby, daty i definicje wskaźników: [`engine.py`](../../backend/prawdowid/engine.py), [`measures.py`](../../backend/prawdowid/measures.py), [`textutil.py`](../../backend/prawdowid/textutil.py).
- Brzmienie krótkiej odpowiedzi: [`answer.py`](../../backend/prawdowid/answer.py); format czatu: [`channels/formatting.py`](../../backend/prawdowid/channels/formatting.py).
- Dostawcy wyszukiwania na żywo: [`websearch.py`](../../backend/prawdowid/websearch.py).
- Pobieranie konkretnego serwisu: [`source_handlers/`](../../backend/prawdowid/source_handlers/), wspólne metody: [`sources/fetchers.py`](../../backend/prawdowid/sources/fetchers.py).
- Maskowanie danych osobowych: [`textutil.py`](../../backend/prawdowid/textutil.py); bezpieczne URL i instrukcje w treści: [`security.py`](../../backend/prawdowid/security.py).
- Historia sprawdzeń, sprawy analityka i usuwanie sesji: [`store.py`](../../backend/prawdowid/store.py).
- Grupy wydawców w katalogu: [`catalog.py`](../../backend/prawdowid/catalog.py). Nie wpływają na kwalifikację źródeł ani ocenę treści.

## Dokumenty opisujące pozostałą część produktu

- [Architektura całego produktu](../ARCHITECTURE.md): WWW, wtyczka, boty, modele i ograniczenia.
- [Model danych](../DATA_MODEL.md): pliki, SQLite, pamięć embeddingów i retencja.
- [Kontrakt rejestru źródeł](../SOURCE_REGISTRY.md): pola konfiguracji, metody pobierania i CLI.
- [Katalog źródeł](../SOURCES.md): wydawcy, kwalifikacja i warunki wykorzystania.
- [Wdrożenie](../DEPLOYMENT.md): Docker, trwałe wolumeny, proxy i HTTPS.
- [Discord](../DISCORD.md): konfiguracja, prywatność, transport i alerty.
- [Koszty](../COSTS.md), [ryzyka](../RISKS.md) i [zgodność konkursowa](../COMPLIANCE.md): uzasadnienia produktowe i stan walidacji.

## Jak czytać ocenę jakości

Istnienie funkcji w kodzie nie jest gwarancją poprawnej odpowiedzi na każde pytanie. Testy jednostkowe sprawdzają kontrakty i zabezpieczenia, scenariusze organizatorów przechodzą przez rzeczywiste modele, a ewaluacja mierzy wyniki na konkretnych zbiorach.

Znane ograniczenia, w tym lokalne wymagania OCR, retencja przy starcie i niepełny korpus, pozostają opisane w [rozwoju i testowaniu](DEVELOPMENT.md). Refaktoryzacja porządkuje kod; nie zmienia reguł weryfikacji ani nie podnosi sama w sobie jakości modeli.
