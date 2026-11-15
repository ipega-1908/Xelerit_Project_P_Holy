# GEMINI.md

Instrukcje dla agentów AI pracujących w tym repozytorium.
Przeczytaj ten plik w całości, zanim zmienisz cokolwiek w kodzie.

## Projekt

Aplikacja webowa, która pomaga kierowcom znaleźć najtańsze paliwo i ocenić, czy dojazd na tańszą stację się opłaca.

- Użytkownicy dodają ceny paliw na stacjach. Każdą cenę można potwierdzić (zielony ptaszek) albo odrzucić (czerwony X, który wymaga podania poprawnej ceny).
- Stacje mają rabaty z aplikacji sieci (np. Orlen Vitay, BPme, Circle K EXTRA). Aplikacja pokazuje cenę ze słupka oraz cenę z rabatem z aplikacji. Jest dla osób, które nie chcą instalować osobnej aplikacji każdej sieci.
- Główna funkcja ("twist"): kalkulator opłacalności objazdu.
  - `detour_cost = extra_km * consumption_per_100km / 100 * price`
  - `savings = liters * (usual_price - cheaper_price)`
  - `net_gain = savings - detour_cost`
  - `min_liters = detour_cost / price_difference` (minimalna liczba litrów, od której objazd się opłaca)
- To zadanie rekrutacyjne (MVP pełnostosowe o tematyce transportu). Ważniejsze od liczby funkcji są: jakość kodu, czysta architektura, poprawny REST, UX i to, że właściciel rozumie każdą linijkę.

## Jak ze mną pracować (najważniejsza sekcja)

Właściciel musi rozumieć cały kod i umieć go obronić na rozmowie rekrutacyjnej.

1. Pracuj małymi krokami. Jeden krok = jedna spójna zmiana (np. jeden moduł domenowy z testami).
2. Po każdym kroku zatrzymaj się, w kilku zdaniach opisz, co zmieniłeś i dlaczego, wypisz ruszone pliki i poczekaj na potwierdzenie. Nie łącz kroków na własną rękę.
3. Nigdy nie generuj całej aplikacji naraz.
4. Wybieraj proste i czytelne rozwiązania zamiast sprytnych. Gdy wybierasz między dwoma podejściami, weź prostsze i jednym zdaniem opisz kompromis.
5. Jeśli wymaganie jest niejasne lub brakuje decyzji, zapytaj. Nie zgaduj i nie wymyślaj funkcji.
6. Nie ruszaj plików niezwiązanych z bieżącym krokiem. Żadnych przy okazji robionych refaktoryzacji.
7. Gdy zmieniasz kontrakt (kształt API, model danych), powiedz o tym wprost i najpierw zapytaj.
8. Nieoczywiste decyzje opisuj w komentarzach w kodzie (dlaczego, a nie co).

## Zakres

W zakresie: stacje, zgłoszenia cen, potwierdzenie/odrzucenie z korektą, rabaty z aplikacji (benefits), kalkulator objazdu i ranking, interfejs po polsku, dane startowe (seed) dla Gdańska.

Poza zakresem, chyba że właściciel wyraźnie o to poprosi: logowanie, role, JWT, migracje bazy (Alembic), cache, kolejki, websockety, Docker (dodajemy dopiero na samym końcu), scrapowanie cudzych serwisów, zewnętrzne API tras, płatności, frameworki i18n.

Mapa (Leaflet) dochodzi dopiero wtedy, gdy wszystko inne działa.

## Stack

- Backend: Python 3.11+, FastAPI, SQLModel, SQLite, pytest
- Frontend: React + Vite + TypeScript
- Osobne foldery: `backend/` i `frontend/`. Rozwój lokalnie, bez Dockera. `docker-compose.yml` dodajemy na końcu jako opcjonalny sposób uruchomienia.
- Kod, identyfikatory, komentarze i komunikaty commitów: po angielsku. Teksty w interfejsie: po polsku.

## Struktura repozytorium

```
backend/
  app/
    main.py          # tworzenie aplikacji, CORS, rejestracja routerów
    routers/         # cienka warstwa HTTP: parsowanie wejścia, wywołanie serwisu, odpowiedź
    services/        # logika korzystająca z bazy, transakcje
    domain/          # czyste funkcje: bez bazy, bez HTTP, bez dostępu do zegara
    models.py        # tabele SQLModel
    schemas.py       # modele Pydantic wejścia/wyjścia API
    seed.py
  tests/
frontend/
  src/
docs/
  AI_LOG.md          # bieżące notatki o użyciu AI (materiał do README)
GEMINI.md
README.md
```

Zasady warstw:
- `domain/` niczego nie importuje z FastAPI, SQLModel ani z bazy. Da się go w pełni testować jednostkowo.
- Routery nie zawierają logiki biznesowej.
- Tabele (`models.py`) i schematy API (`schemas.py`) są rozdzielone. Nie zwracaj modeli tabel bezpośrednio z endpointów.

## Reguły domenowe

- Cen nigdy nie nadpisujemy. Każde zgłoszenie i korekta to nowy `PriceReport`, a historia zostaje. Obowiązującą cenę wybiera konsensus (sekcja "Weryfikacja i ustalanie ceny"), a nie najnowszy raport.
- Odrzucenie ceny z korektą to JEDNA transakcja: `PriceVote(reject)` na starym raporcie plus nowy `PriceReport`.
- Walidacja korekty: cena w zakresie 3,00-15,00 zł i różna od poprzedniej (identyczna cena powinna być potwierdzeniem).
- Jeden głos użytkownika na raport (unikalność `report_id` + `user_id`). Powtórny głos zwraca 409.
- Rabaty (benefits) to dane z datami ważności, a nie stałe w kodzie. Rabat ma `valid_from`, `valid_to` i `checked_at`.
- Rabat z `max_liters` działa tylko do tego limitu: `discount * min(liters, max_liters)`.
- Świeżość ceny: udostępniaj wiek ceny i prosty wskaźnik zaufania (liczba potwierdzeń i wiek). Kalkulator ostrzega, gdy najtańsza cena jest stara lub niepotwierdzona.
- Dystans: haversine razy współczynnik drogi (domyślnie 1,3). To udokumentowane uproszczenie.

### Obsługa czasu

- Wszystkie znaczniki czasu (`reported_at`, `created_at`) ustawia serwer. Nigdy nie ufaj zegarowi klienta.
- W bazie trzymamy wszystko w UTC.
- Dni tygodnia i godziny w regułach rabatów liczymy w strefie `Europe/Warsaw` (użyj `zoneinfo`). Przykład: piątek 23:30 w Polsce to w UTC już sobota, a reguła musi mimo to zadziałać poprawnie.
- Każda funkcja zależna od bieżącego czasu przyjmuje parametr `now`. Nigdy nie wołaj zegara wewnątrz `domain/`.

## Weryfikacja i ustalanie ceny

Nie da się w pełni sprawdzić, czy cena jest prawdziwa, więc niepewne ceny oznaczamy, a nie ukrywamy. Cała logika to czyste funkcje w `domain/` (przyjmują `now`). Progi są stałymi w jednym miejscu.

- `MAX_DEVIATION_PLN = 1.0`, `MIN_CONFIRMATIONS = 2`, `CONSENSUS_WINDOW_DAYS = 3`, minimum 3 stacje w okolicy do porównania, promień porównania 10 km.
- Walidacja zakresu: 3,00-15,00 zł (patrz reguły domenowe).
- Test wiarygodności: porównaj cenę z medianą świeżych cen tego samego paliwa na innych stacjach w promieniu 10 km. Odchylenie powyżej 1 zł w obie strony oznacza status `suspicious`. Zgłoszenie NIE jest odrzucane, tylko oznaczone. Jeśli w okolicy jest mniej niż 3 stacje z ceną, status to `unconfirmed`, nie `suspicious`.
- Konsensus: bierzemy zgłoszenia danego paliwa na danej stacji z ostatnich `CONSENSUS_WINDOW_DAYS` dni i grupujemy po cenie. Poparcie ceny = liczba RÓŻNYCH użytkowników, którzy ją zgłosili lub potwierdzili, minus ci, którzy ją odrzucili (X). Obowiązuje cena z największym poparciem, a przy remisie nowsza. Dzięki temu prawdziwa podwyżka szybko wygrywa ze starą ceną.
- Statusy ceny: `verified` (poparcie co najmniej `MIN_CONFIRMATIONS` od różnych osób), `unconfirmed`, `suspicious`. Cena `suspicious` pozostaje taka, dopóki nie pojawi się korekta lub więcej potwierdzeń. Status wygasa z wiekiem ceny.
- Autor zgłoszenia nie może potwierdzić własnej ceny. Nowa cena z korekty zaczyna z zerem potwierdzeń.
- Kalkulator ostrzega, gdy zysk opiera się na cenie `suspicious` lub `unconfirmed` albo starej.
- Funkcja `resolve_current_price(reports, votes, now)` zastępuje zasadę "najnowszy raport". Testy: podwyżka po serii odrzuceń, remis, głosy poza oknem czasowym, ten sam użytkownik głosujący dwa razy, mało stacji w okolicy.

## Lokalizacja

- Demo NIE używa przeglądarkowego Geolocation API. Punkt startu użytkownik wybiera ręcznie: domyślnie centrum Gdańska, z możliwością wyboru dzielnicy z listy (a po dodaniu mapy kliknięcia na mapie).
- Współrzędne punktu startu wysyłamy tylko w zapytaniu `/deals` i nigdzie ich nie zapisujemy.

## Ograniczenia dema (mają trafić do README)

Agent ma pilnować, żeby te ograniczenia były w README w sekcji "Ograniczenia demo i dalszy rozwój":

- brak prawdziwej geolokalizacji (punkt startu wybierany ręcznie)
- brak logowania: `X-User-Id` generuje przeglądarka, więc głosy można nadużywać
- ceny i rabaty są przykładowe i nie aktualizują się same
- odległość to haversine razy współczynnik, a nie prawdziwa trasa
- stały próg 1 zł nie skaluje się z poziomem cen (np. dla LPG jest bardzo luźny)
- brak automatycznego pobierania cen z oficjalnych źródeł

## Konwencje API

- REST, ścieżki oparte na zasobach (rzeczowniki, nie czasowniki).
  - `GET/POST /stations`, `GET/PUT/DELETE /stations/{id}`
  - `GET/POST /stations/{id}/price-reports`
  - `POST /price-reports/{id}/confirmations`
  - `POST /price-reports/{id}/corrections`
  - `GET/POST/PUT/DELETE /benefits`, `/benefits/{id}`
  - `GET /deals?lat&lon&fuel&liters&consumption&apps`
- Poprawne kody statusu: 200, 201, 204, 404, 409, 422.
- Walidacja wejścia przez Pydantic. Spójny format błędów.
- CORS skonfigurowany jawnie dla adresu frontendu (w wersji końcowej bez wildcarda).
- Tożsamość użytkownika: nagłówek `X-User-Id` (UUID generowany w przeglądarce). To świadome uproszczenie, opisane w README. To nie jest prawdziwa autoryzacja.
- Profil auta (spalanie, bak) i lista aplikacji, które użytkownik ma, trzymamy we frontendzie (localStorage) i wysyłamy w zapytaniu.

## Testy

- Najpierw testy czystej logiki domenowej, potem testy API.
- Minimalne wymagane przypadki: zysk netto i minimalne litry (w tym zerowa różnica cen), rabat z limitem litrów, reguła weekendowa w piątek 23:30 czasu warszawskiego, walidacja korekty, podwójny głos zwraca 409, korekta jest atomowa.
- Testy używają bazy SQLite w pamięci i nigdy nie zależą od prawdziwego zegara.
- Przed zgłoszeniem kroku jako gotowego uruchom `pytest` i uczciwie podaj wynik.

## Styl kodu

- Python: podpowiedzi typów wszędzie, małe funkcje, opisowe nazwy, formatowanie `ruff format`, lintowanie `ruff check`.
- TypeScript: tryb strict, bez `any`, typowany klient API w jednym miejscu, małe i wyspecjalizowane komponenty, bez logiki biznesowej w JSX.
- Bez martwego i zakomentowanego kodu, bez nieużywanych zależności.
- Dodawaj zależność tylko wtedy, gdy jest potrzebna, i wspomnij o tym.

## UX

- Interfejs po polsku, czytelny i szybki w użyciu. Potwierdzenie ceny to jedno kliknięcie, a X od razu pyta o poprawną cenę.
- Przy każdej stacji pokazuj obie ceny: ze słupka i z aplikacji sieci, a do tego warunki (limit litrów, dni) oraz wiek ceny.
- Obsłuż stany ładowania, pustej listy i błędu w każdym widoku.
- Interfejs ma być czysty i spójny, a nie przeładowany funkcjami.

## Dane

- Seed: 12-15 prawdziwych stacji z Gdańska z kilku sieci. Ceny są fikcyjne i w README muszą być opisane jako przykładowe.
- Rabaty wpisujemy ręcznie z datą `checked_at`. Zmieniają się często i wymagają okresowej aktualizacji.
- Żadnego scrapowania cudzych serwisów.

## Git

- Małe commity, jedna logiczna zmiana w każdym, komunikaty po angielsku w trybie rozkazującym.
- Nigdy nie commituj sekretów, plików `.env`, pliku bazy SQLite, `node_modules` ani `.venv`.
- Ten plik i `docs/AI_LOG.md` mają być w repozytorium (wymaga tego zadanie).

## Dziennik użycia AI

Po każdym ukończonym kroku dopisz krótki wpis do `docs/AI_LOG.md`: o co poproszono, co wygenerował agent i co właściciel zmienił lub odrzucił. Z tego powstanie sekcja o pracy z AI w README.

## Kiedy krok jest skończony

- Kod robi to, o co poproszono, i nic więcej.
- Testy do tego kroku istnieją i przechodzą.
- Żadne niezwiązane pliki nie zostały zmienione.
- Podsumowanie dla właściciela wymienia ruszone pliki i każdą decyzję wymagającą potwierdzenia.
