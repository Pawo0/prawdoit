# Audyt dowodów dla każdej tezy odpowiedzi

Ten audyt oddziela obecność źródła, semantyczne wsparcie pojedynczej tezy i poprawność wybranego cytatu. Nie importuje silnika Prawdowida, modelu NLI ani jego reguł do oceny semantycznej. O wyniku relacji teza–dowód decyduje jawna adnotacja recenzenta.

## Co jest jednostką pomiaru

Jednostką jest **atomowe ustalenie faktograficzne w odpowiedzi systemu**, także w długim wyjaśnieniu i brakującym kontekście. Werdykt odnosimy do tezy użytkownika z właściwą polaryzacją: „fałszywe” dla „X” oznacza odrzucenie X, nie przyjęcie X. Liczby, daty, podmioty i zakres nie mogą zostać dopowiedziane na podstawie samego podobieństwa tematu.

Rozdzielamy niezależne ustalenia, np. „wygrał wybory” oraz „otrzymał 50,89%”. Powtórzenie tego samego ustalenia w krótkiej odpowiedzi, wyjaśnieniu i podsumowaniu liczymy raz w obrębie jednej odpowiedzi. Surowo przytoczona pogłoska użytkownika lub źródła nie staje się automatycznie ustaleniem systemu.

Inwentaryzujemy wszystkie powierzchnie tekstowe: ocenę, krótką odpowiedź, wyjaśnienie, kontekst, opis niewiedzy, propozycję rozstrzygającego dowodu, przesłanki, ograniczenia i podsumowania. Metadane bibliograficzne, nawigacja/rekomendacje zasobów, instrukcje dla użytkownika i opis działania systemu są jawnie klasyfikowane poza mianownikiem **ustaleń o sprawdzanym doniesieniu**. Sama abstynencja lub opinia bez ustalenia o świecie nie jest zaliczana jako „poprawnie zacytowana teza”. Nie oceniamy tu prawdziwości wszystkich stałych etykiet interfejsu, statusu serwera ani adekwatności katalogowych rekomendacji instytucji.

Pełny tekst źródła służy do ustalenia pochodzenia i kontekstu. Nie wolno nim naprawiać oceny cytatu, który w pokazanym fragmencie nie zawiera uzasadnienia.

## Trzy osobne miary

1. **Obecność odnośnika** = tezy z przypisanym źródłem / wszystkie zinwentaryzowane tezy. Ta miara sama nie oznacza pokrycia dowodem.
2. **Pokrycie tezy dowodem** = tezy mające przynajmniej jeden wystarczający, zweryfikowany dowód / wszystkie zinwentaryzowane tezy. Tezy bez źródła pozostają w mianowniku. Cel konkursowy: ≥95%.
3. **Poprawność cytowania** = wystarczająco wspierające powiązania teza–cytat / wszystkie ocenione powiązania teza–cytat. Cel: ≥85%. „Partial”, „unsupported”, „contradicted” i „unassessable” nie są zaliczane do poprawnych.

Dodatkowo raportujemy poprawność wszystkich powiązań dowodowych, także metadanych i kart danych. Atrybucję „wydawca ocenił X jako fałsz” można sprawdzić z opublikowaną etykietą i sprawdzaną tezą. Taka poprawna atrybucja nie zastępuje dowodu dla osobnego ustalenia „X jest fałszywe”.

Metadane i automatyczne karty danych nie zwiększają mianownika dosłownych cytatów. Karty traktujemy jako zapisane opisy danych; ich zgodność z rekordem nie potwierdza ponownie obliczeń ani danych pierwotnych instytucji. Sprawdzenie dosłowności fragmentu względem zamrożonego rekordu jest osobną, mechaniczną kontrolą.

Dla tezy przedstawionej jako konflikt źródeł trzeba pokazać rozbieżne ustalenia **tej samej sprawy, zakresu i czasu**. Sama obecność dwóch różnych publikacji lub dwóch różnych liczb nie wystarcza.

## Zamrożenie odpowiedzi i źródeł

```bash
PRAWDOWID_RUNTIME_DIR=/tmp/citation-runtime \
PRAWDOWID_INDEX_DIR=/tmp/citation-index \
PRAWDOWID_SCHEDULER=0 PRAWDOWID_LIVE_SEARCH=0 \
  backend/.venv/bin/python eval/run_eval.py \
  --cases eval/cases.jsonl --citation-audit --out /tmp/citation-capture
```

Użyj świeżego runtime i kopii `data/index/`, jak opisano w [instrukcji ewaluacji](../../docs/backend/DEVELOPMENT.md). Wynik zawiera pełne `responses.jsonl`, teksty przywołanych dokumentów `citation_sources.jsonl` i skróty SHA-256. Wspólna ewaluacja nadal wykonuje swoje kontrole jakości i kanałów; samo zamrożenie nie nadaje ocen semantycznych.

## Przygotowanie próby i niezależna recenzja

```bash
python3 eval/citations/run.py prepare \
  --capture /tmp/citation-capture --out /tmp/citation-review \
  --sample-size 30 --seed 20261122
```

Losowanie jest deterministyczne, bez zwracania, z równomiernym doborem z warstw wyniku, wejść wielowątkowych i braku twierdzeń. Po wyczerpaniu małej warstwy pozostałe nadal dostarczają przypadki. Nie jest to prosta próba losowa z populacji ani estymata ważona całej populacji.

Recenzent otrzymuje `packets.jsonl`: wejście, tekst odpowiedzi, pokazane cytaty, bibliografię i zamrożone źródła. Nie otrzymuje oczekiwanych wyników zbioru, notatek autorów testów ani wewnętrznych etykiet stance. Liczby NLI, jeśli występują w samej prezentowanej użytkownikowi przesłance, pozostają tekstem do zinwentaryzowania; nie są regułą oceniania.

`sampling_map.jsonl` jest przeznaczony dla koordynatora do odtworzenia przypadków. Do recenzji niezależnej od wcześniejszej oceny nie przekazuj recenzentowi ocen AI ani tej mapy. Przykład adnotacji i pusty formularz dla obecnego pomiaru są w katalogu [review](../citation_audit_2026-11-22/review/).

Recenzent:

1. Oznacza każdą powierzchnię jako faktograficzną/mieszaną, proceduralną, niefaktograficzną albo powtórzenie wskazanego pola.
2. Wypisuje wszystkie atomowe ustalenia o świecie. Dla każdego wskazuje fragment odpowiedzi (`anchor`) i powierzchnie, w których się pojawia.
3. Wskazuje źródła rzeczywiście przywołane w odpowiedniej części odpowiedzi. Źródło z innego twierdzenia lub pominięta karta nie może automatycznie zapewnić pokrycia.
4. Ocenia osobno każdą relację: `supported`, `partial`, `unsupported`, `contradicted`, `unassessable`. Uzasadnia ocenę i wskazuje dokładny wspierający fragment lub zweryfikowane pole źródła.
5. Potwierdza kompletność inwentarza. Podaje własną tożsamość/pseudonim oraz rzeczywisty typ recenzenta. Oceny AI nie oznaczamy jako `independent_human`.

Przy sporach potrzebny jest drugi niezależny przegląd i rozstrzygnięcie z zachowaniem obu ocen. Nowa próba po poprawkach powinna być oddzielna od próby użytej do tych poprawek.

## Obliczenie wyniku

```bash
python3 eval/citations/run.py score \
  --packets /tmp/citation-review/packets.jsonl \
  --reviews /tmp/citation-review/reviews.jsonl \
  --out /tmp/citation-review/report.json

python3 eval/citations/test_protocol.py
```

Skrypt odrzuca m.in. zmieniony pakiet, brak oceny powierzchni, pominięte faktyczne pole, nieistniejącą kotwicę, dowód z innego twierdzenia i wspierający fragment nieobecny w pokazanym cytacie. Walidacja działa także z `python -O`. Kompletność atomizacji wewnątrz zdania nadal wymaga rzetelnego recenzenta; nie da się potwierdzić jej samym schematem JSON.

Przy niepełnej recenzji próby raport nie potwierdza progów. Brak tez lub cytowań daje `null`, nie automatyczne 100%. Wynik zawiera liczniki i listę niepokrytych tez, dzięki czemu da się go ponownie przeliczyć bez modeli.

## Relacja do starego runnera

`eval/run_eval.py` przechowuje dawną kontrolę jako **`citation_presence_proxy`**. Pola `citation_coverage` i `citation_correctness` pozostają `null`, dopóki nie ma osobnego audytu adnotacji. Runner nie przedstawia już obecności jakiegokolwiek materiału — także kontekstu — jako spełnienia celu 95%.

Aktualny audyt: [wyniki i wnioski](../../docs/CITATION_AUDIT.md). To audyt wsparcia odpowiedzi w zamrożonych materiałach, nie niezależna weryfikacja prawdziwości świata ani praw do wszystkich danych.
