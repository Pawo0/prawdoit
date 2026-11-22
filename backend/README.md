# Backend Prawdowida

Backend to aplikacja FastAPI i wspólny silnik weryfikacji dla WWW, wtyczki oraz adapterów kanałów. Kod produkcyjny jest w `prawdowid/`, testy w `tests/`.

## Czytanie kodu

Zacznij od [przewodnika backendu](../docs/backend/README.md). Następnie przeczytaj `prawdowid/service.py`, gdzie `run_check()` pokazuje etapy całego sprawdzenia, oraz `prawdowid/engine.py`, gdzie `verify_claim()` prowadzi ocenę pojedynczej tezy.

- [Przebieg sprawdzenia](../docs/backend/REQUEST_FLOW.md)
- [Silnik i dowody](../docs/backend/ENGINE.md)
- [Źródła i wyszukiwanie](../docs/backend/SOURCES.md)
- [API i kanały](../docs/backend/API.md)
- [Rozwój i testowanie](../docs/backend/DEVELOPMENT.md)
- [Mapa wszystkich modułów](../docs/backend/MODULES.md)

## Uruchomienie

Instalację modeli i zależności oraz start lokalnego API opisuje [README projektu](../README.md). Gotowy kontener, tokeny paneli, HTTPS i wolumeny opisuje [wdrożenie](../docs/DEPLOYMENT.md). Dokumentacja HTTP po uruchomieniu jest pod `/docs`.

Konfiguracja jest odczytywana ze zmiennych środowiskowych podczas importu. Ustaw katalog runtime i wyłączenie harmonogramu przed zaimportowaniem aplikacji w testach. Sam import warstwy danych może utworzyć bazę SQLite.

## Narzędzia programisty

`requirements.txt` zawiera zależności backendu, `requirements-container.txt` wersje używane do budowania obrazu, a `requirements-dev.txt` wyłącznie formatter i analizator kodu. `pyproject.toml` ustawia formatowanie na 100 znaków i składnię Pythona 3.12.

Polecenia testów, formatowania i pomiarów są w [DEVELOPMENT.md](../docs/backend/DEVELOPMENT.md). Zwróć uwagę na różnicę między szybkimi testami bez modeli a scenariuszami, które uruchamiają rzeczywistą inferencję.
