# Silnik weryfikacji i dowody

[`engine.verify_claim()`](../../backend/prawdowid/engine.py) ocenia jedno `Claim`. Zwraca `ClaimResult` zawierający klasę wyniku, dowody, jawne przesłanki, kody reguł i ograniczenia. Nie pobiera dowolnych stron ani nie korzysta z LLM do wyznaczenia werdyktu.

## Przygotowanie kandydatów

1. `_retrieve_candidates()` koduje zapytanie i łączy dopasowania sprawdzonych twierdzeń z hybrydowym wyszukiwaniem fragmentów. Wyniki są scalane po dokumencie i ograniczane do najbardziej obiecujących kandydatów.
2. `_select_candidate_fragments()` wybiera dosłowne fragmenty dokumentów. Uwzględnia pytania o konkretne kwoty, czas pochodzenia starego materiału oraz dopasowanie do jednego zdania dłuższej wypowiedzi.
3. `_score_candidate_stances()` przygotowuje pary tekstów do NLI. Oddziela podobieństwo od wynikania lub sprzeczności. Dla odpowiednich danych urzędowych stosuje porównania liczb i dat, ponieważ sam model NLI nie jest w nich wystarczająco pewny.

Wewnętrzny obiekt `_Cand` przechowuje indeks dokumentu, znaleziony fragment, podobieństwa i wyniki kolejnych ocen. To roboczy stan analizy, nie publiczny schemat odpowiedzi. Jego dotychczasowa nazwa i pola są zachowane dla zgodności testów.

## Indeks i modele

[`index.py`](../../backend/prawdowid/index.py) odpowiada za wczytanie dokumentów, podział na fragmenty, BM25 i wektory. `CorpusIndex` udostępnia także indeks twierdzeń z fact-checków oraz przyrostowe dodawanie dokumentów. Pliki embeddingów są cache, nie źródłem prawdy.

`INDEX` jest obiektem współdzielonym przez proces. Aktualizacja źródeł może przeładować indeks, a live-search może dołączyć dokumenty. Rozmiar i zawartość korpusu wpływają na wynik testów, dlatego pomiar jakości powinien wskazywać wersję kodu, modeli i danych.

[`nli.py`](../../backend/prawdowid/nli.py) ładuje model leniwie. Ocenia relację między dwoma tekstami: poparcie, neutralność lub sprzeczność. Embedding służy do wyszukania podobnego materiału, NLI do oceny jego relacji, a reguły do decyzji. Te role nie są zamienne.

## Od podobnego materiału do dowodu

Podobny artykuł może dotyczyć innej osoby, liczby lub okresu. Dlatego [`agreement.py`](../../backend/prawdowid/agreement.py), porównania tematu i zabezpieczenia w `engine.py` sprawdzają zgodność istotnych elementów.

Osobno obsługiwane są:

- ta sama sprawdzona teza i jej zaprzeczenie;
- jedno zdanie dłuższej wypowiedzi;
- inne definicje wskaźnika, np. różne miary inflacji;
- data wejścia przepisu w życie;
- stare nagranie przedstawione jako bieżące;
- rekord zawierający tylko metadane ClaimReview, bez własnego fragmentu ustalenia;
- pytanie o identyczność podlinkowanego materiału, obsługiwane w `provenance.py`.

[`measures.py`](../../backend/prawdowid/measures.py) rozpoznaje definicje wskaźników. [`textutil.py`](../../backend/prawdowid/textutil.py) udostępnia wspólne operacje na polskim tekście, kwotach, jednostkach i datach.

## Grupy dowodów i kolejność decyzji

Po przygotowaniu kandydaci są klasyfikowani jako popierający, przeczący, wskazujący wprowadzenie w błąd, nieweryfikowalni lub kontekstowi. Fragment wyświetlany użytkownikowi musi być zgodny z zapisanym materiałem. Przy dopasowaniu do zaprzeczenia cytat może być dobierany ponownie, aby nie powtarzać ustalenia dotyczącego przeciwnej tezy.

`_decide()` ma celowo uporządkowane reguły. W skrócie:

- R1: opinie i prognozy nie otrzymują faktograficznego rozstrzygnięcia.
- R2: sprzeczne kwalifikujące się dowody wymagają ujawnienia konfliktu i wstrzymania się.
- R3: odpowiednie dowody przeczące prowadzą do wyniku „fałszywe”; R3a opisuje fałszywy kontekst starego materiału.
- R4: wynik „wprowadzające w błąd” obejmuje odpowiednią ocenę fact-checkera oraz określone przypadki archiwalnego kontekstu.
- R5: odpowiednie dowody popierające pozwalają potwierdzić tezę.
- Przy braku wystarczającej podstawy pozostaje abstynencja i opis potrzebnego dowodu; dalsze przesłanki obejmują m.in. ryzyko i ograniczenia.

To opis nawigacyjny, nie alternatywna implementacja progów. Dokładna kolejność, warunki i identyfikatory są w kodzie. Źródła urzędowe i fact-checkingowe mogą stanowić podstawę rozstrzygnięcia; sam wpis w bazie incydentów lub materiał medialny nie wystarcza.

Nazwy reguł, `reason_codes` i pola dowodów są częścią audytu. Zmieniając ich znaczenie, trzeba rozważyć wersję reguł, testy i zgodność zapisanych analiz.

## Siła podstawy odpowiedzi

Siła uwzględnia typ źródła, zgodność fragmentu, wiek materiału, konflikty i liczbę grup wydawców. Grupowanie po wydawcy przybliża niezależność; dwie redakcje cytujące jedną depeszę nie muszą być dwoma niezależnymi ustaleniami.

W interfejsie podstawę wyjaśnia lista `premises` i etykieta słowna. Wartości podobieństwa i NLI są sygnałami modelu, nie prawdopodobieństwem prawdziwości świata.

## Odpowiedź dla człowieka

[`answer.py`](../../backend/prawdowid/answer.py) wybiera główny dowód i tworzy krótką odpowiedź, podstawę oraz ograniczenie. Materiał pokrewny przy abstynencji pozostaje oznaczony jako nierozstrzygający. [`channels/formatting.py`](../../backend/prawdowid/channels/formatting.py) przenosi ten wynik do wiadomości czatu.

Opcjonalny [`llm.py`](../../backend/prawdowid/llm.py) upraszcza gotowe wyjaśnienie. Jego walidacja odrzuca m.in. nowe liczby, URL i zbyt długi tekst; nie jest pełną walidacją wszystkich faktów i nazw. Domyślna ścieżka działa bez tego modelu.

## Jak bezpiecznie zmienić regułę

Najpierw opisz rodzaj błędu na przykładzie niezależnym od scenariuszy konkursowych. Dodaj regresję obejmującą także podobny tekst, którego reguła nie powinna obsłużyć. Uruchom testy jednostkowe i scenariusze rzeczywistych modeli, a następnie obejrzyj cytat i uzasadnienie, nie tylko etykietę końcową. Procedurę opisuje [rozwój i testowanie](DEVELOPMENT.md).
