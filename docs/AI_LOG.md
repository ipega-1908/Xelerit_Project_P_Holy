# AI Usage Log

Bieżący dziennik wykorzystania asystenta AI podczas pracy nad projektem.

## Krok 0: Analiza wymagań i planowanie
- **O co poproszono:** Przegląd `GEMINI.md` pod kątem sprzeczności i luk, przygotowanie planu implementacji w małych krokach oraz lista pytań przed startem.
- **Co wygenerował agent:** Zidentyfikowano 4 kwestie do doprecyzowania (stacja odniesienia i `extra_km` w kalkulatorze, zachowanie po upływie 3-dniowego okna konsensusu, lista obsługiwanych paliw, menedżer pakietów) oraz 12-krokowy plan implementacji.
- **Decyzje właściciela:**
  1. W kalkulatorze punktem odniesienia (`usual_price`) jest najbliższa stacja z ceną danego paliwa, `extra_km = max(0, 2 * (dystans_do_stacji - dystans_do_najbliższej))`, a koszt zużytego paliwa na objazd liczymy po `cheaper_price`.
  2. Jeśli mamy jakiekolwiek starsze zgłoszenie (> 3 dni), pokazujemy je ze statusem `expired`; jeśli brak jakiegokolwiek zgłoszenia – zwracamy brak ceny (`unknown` / `None`). Pojedyncze zgłoszenie od użytkownika od razu traktujemy jako obowiązującą cenę na stacji.
  3. Zestaw paliw: `PB95`, `PB98`, `ON`, `LPG`.
  4. Menedżer pakietów w backendzie: `uv`.

## Krok 1: Szkielet repozytorium i konfiguracja narzędzi
- **O co poproszono:** Utworzenie szkieletu katalogów, konfiguracji `uv` (`pyproject.toml`), `.gitignore`, `docs/AI_LOG.md` oraz testu dymnego (`test_smoke.py`).
- **Co wygenerował agent:** Pliki konfiguracyjne projektu (`backend/pyproject.toml` z FastAPI, SQLModel, `tzdata`, `pytest`, `httpx`, `ruff`), `.gitignore` oraz pusty pakiet `backend/app`.
- **Zmiany właściciela:** Zaakceptowano; ustalono wykonywanie poziomu `domain/` po jednym module.

## Krok 2: `domain/` – Dystans i kalkulator opłacalności objazdu
- **O co poproszono:** Implementacja czystych funkcji obliczania dystansu (Haversine * 1.3, dodatkowy objazd względem stacji bazowej) oraz kalkulatora opłacalności z limitem litrów rabatu (`max_liters`) wraz z testami jednostkowymi.
- **Co wygenerował agent:** Moduły `distance.py`, `calculator.py` oraz testy `test_domain_calculator.py` (w tym przypadki brzegowe: zerowa/ujemna różnica cen, przekroczenie `max_liters`).
- **Zmiany właściciela:** Zaakceptowano; przejście do kolejnego modułu `domain/`.

## Krok 3: `domain/` – Reguły rabatów i strefa czasowa `Europe/Warsaw`
- **O co poproszono:** Implementacja czystych funkcji oceny aktywności rabatów z użyciem `zoneinfo` (`Europe/Warsaw`) oraz wyboru najkorzystniejszego rabatu dla posiadanych aplikacji sieci.
- **Co wygenerował agent:** Moduł `benefits.py` (`BenefitRule`, `is_benefit_active`, `select_best_benefit`) i testy `test_domain_benefits.py` (m.in. granica weekendu w piątek 23:30 czasu warszawskiego i UTC, zmiana czasu lato/zima, wygasłe rabaty, wybór rabatu pod kątem `max_liters`).
- **Zmiany właściciela:** Zaakceptowano; przejście do ostatniego modułu `domain/`.

## Krok 4: `domain/` – Weryfikacja cen i algorytm konsensusu
- **O co poproszono:** Implementacja czystej logiki walidacji cen/korekt, wykrywania podejrzanych odchyleń oraz algorytmu `resolve_current_price(reports, votes, now)` wraz z testami jednostkowymi.
- **Co wygenerował agent:** Moduł `consensus.py` (stałe progowe, statusy `verified`/`unconfirmed`/`suspicious`/`expired`/`unknown`, zliczanie poparcia unikalnych użytkowników, blokada samopotwierdzeń) oraz 8 testów w `test_domain_consensus.py`.
- **Zmiany właściciela:** Zaakceptowano; przejście do małych kroków dla warstwy bazy danych i API.

## Krok 5: Modele SQLModel, połączenie z bazą i seed dla Gdańska
- **O co poproszono:** Utworzenie tabel (`Station`, `PriceReport`, `PriceVote`, `Benefit`), konfiguracji SQLite (`PRAGMA foreign_keys=ON`) oraz skryptu seedującego z 14 stacjami w Gdańsku, przykładowymi cenami i rabatami.
- **Co wygenerował agent:** Pliki `database.py`, `models.py`, `seed.py` i testy `test_seed.py` (idempotentność seeda i test unikalnego indeksu `report_id + user_id`).
- **Zmiany właściciela:** Zaakceptowano; przejście do Kroku 6.

## Krok 6: Schematy API oraz CRUD `/stations` i `/benefits`
- **O co poproszono:** Rozdzielenie modeli tabel od schematów Pydantic, budowa serwisów i cienkich routerów dla stacji (z rozwiązanymi cenami i aktywnymi rabatami) oraz rabatów sieci, wraz z konfiguracją FastAPI i testami API.
- **Co wygenerował agent:** `dependencies.py`, `schemas.py`, `services/pricing.py`, `services/stations.py`, `services/benefits.py`, `routers/stations.py`, `routers/benefits.py`, `main.py`, `tests/conftest.py` oraz `tests/test_api_stations_benefits.py`.
- **Zmiany właściciela:** Zaakceptowano; przejście do kolejnych kroków z zatrzymywaniem tylko w razie błędu testów.

## Krok 7: Zgłoszenia cen, potwierdzenia i atomowe korekty (`/price-reports`)
- **O co poproszono:** Endpointy historii/dodawania raportów cenowych, potwierdzeń (`confirmations`) i atomowych korekt (`corrections`) z identyfikacją nagłówkiem `X-User-Id`.
- **Co wygenerował agent:** `get_user_id` w `dependencies.py`, schematy raportów/głosów/korekt, `services/price_reports.py`, `routers/price_reports.py` oraz testy `test_api_price_reports.py` (409 przy podwójnym głosie i samopotwierdzeniu, 422 przy identycznej korekcie, atomowość transakcji).
- **Zmiany właściciela:** Zatwierdzono automatycznie (wszystkie testy przeszły).

## Krok 8: Ranking opłacalności objazdu (`GET /deals`)
- **O co poproszono:** Endpoint łączący aktualne ceny z konsensusu, rabaty z aplikacji dla podanych `apps`, dystans objazdu oraz ostrzeżenia o niepewnych/przeterminowanych cenach.
- **Co wygenerował agent:** Schematy `DealItemRead`/`DealsResponse`, `services/deals.py`, `routers/deals.py` (obsługa `apps` jako wielokrotnego parametru lub rozdzielonego przecinkiem) i testy `test_api_deals.py`.
- **Zmiany właściciela:** Zatwierdzono automatycznie (wszystkie testy przeszły).

## Krok 9–11: Frontend (React + Vite + TypeScript strict)
- **O co poproszono:** Polskojęzyczny interfejs ze ścisłym typowaniem TS: typowany klient API z `X-User-Id` i profilem auta w `localStorage`, wybór dzielnicy Gdańska, lista stacji z potwierdzaniem (✓) / korektą (✕) i dodawaniem cen oraz kalkulator opłacalności objazdu.
- **Co wygenerował agent:** Konfigurację Vite/TS (`tsconfig.json` w trybie `strict`), `types/api.ts`, `api/client.ts`, `hooks/useUserProfile.ts`, `constants/gdanskDistricts.ts`, `utils/formatters.ts` oraz wyspecjalizowane komponenty (`CalculatorPanel`, `DealsRankingList`, `DealCard`, `StationCard`, `PriceCorrectionForm`, `NewPriceReportForm`, `PriceStatusBadge`).
- **Zmiany właściciela:** Zatwierdzono automatycznie (weryfikacja przez `tsc --noEmit` i `vite build`).

## Krok 12: Dokumentacja (`README.md`) i konteneryzacja (`docker-compose.yml`)
- **O co poproszono:** Przygotowanie dokumentacji końcowej ze wszystkimi wymaganymi ograniczeniami dema, opisem konsensusu i instrukcją uruchomienia oraz opcjonalnej konfiguracji Docker Compose.
- **Co wygenerował agent:** `README.md`, `backend/Dockerfile`, `backend/.dockerignore`, `frontend/Dockerfile`, `frontend/.dockerignore` oraz `docker-compose.yml`.
- **Zmiany właściciela:** Zaakceptowano; rozszerzenie UI o mapę Leaflet.

## Krok 13: Mapa Leaflet (wybór punktu startu i podgląd stacji)
- **O co poproszono:** Dodanie interaktywnej mapy Gdańska (Leaflet) z podglądem stacji oraz możliwością ustawienia punktu startu kliknięciem na mapie.
- **Co wygenerował agent:** Zależność `leaflet` + `@types/leaflet`, komponent `GdanskMap.tsx`, integracja z `CalculatorPanel.tsx` i `App.tsx` (współrzędne z mapy trzymane wyłącznie w stanie tymczasowym i wysyłane tylko do `/deals`).
- **Zmiany właściciela:** Zgłoszono nieczytelny komunikat przy wyborze punktów oddalonych poza Gdańsk (np. Pruszcz Gdański), gdy żaden objazd się nie opłaca.

## Krok 14: Poprawka komunikatów kalkulatora dla punktów oddalonych i stacji bazowej
- **O co poproszono:** Doprecyzowanie werdyktu i komunikatów na kartach, gdy użytkownik wybiera punkt oddalony (np. Pruszcz Gdański) lub żaden objazd nie jest opłacalny.
- **Co wygenerował agent:** Czytelny werdykt w `DealsRankingList.tsx` (informacja o braku opłacalnego objazdu, najbliższej stacji do progu opłacalności, oddaleniu od zasięgu bazy >5 km i statusie przeliczania), rozróżnienie stacji bazowej od nieopłacalnego objazdu w `DealCard.tsx` oraz centrowanie mapy przy powrocie do dzielnicy w `GdanskMap.tsx`.
- **Zmiany właściciela:** Zaakceptowano; rozszerzenie o pełny CRUD w UI oraz funkcję AI odczytu cen ze zdjęcia.

## Krok 15: Pełny CRUD stacji i rabatów w UI oraz odczyt cen ze zdjęcia (AI)
- **O co poproszono:** Dodanie brakującego CRUD-u stacji i rabatów w interfejsie oraz prostej funkcji AI odczytującej ceny paliw ze zdjęcia słupka przy dodawaniu nowej stacji i zgłaszaniu ceny (w trybie demo bez klucza API).
- **Co wygenerował agent:** Backend `domain/price_extraction.py`, `services/ai_extractor.py`, `routers/ai.py` (`POST /ai/extract-prices`, tryb demo offline + opcjonalny `GEMINI_API_KEY`), testy `test_api_ai_extract.py`; frontend `StationForm.tsx`, `BenefitForm.tsx`, `BenefitsView.tsx`, `utils/imageUpload.ts`, rozbudowa `StationCard.tsx`, `NewPriceReportForm.tsx` i `App.tsx`.
- **Zmiany właściciela:** Poprosił o zamianę ręcznego wpisywania współrzędnych w formularzu stacji na wskazywanie lokalizacji na mapie.

## Krok 16: Wybór lokalizacji stacji kliknięciem na mapie
- **O co poproszono:** Zastąpienie ręcznych pól `latitude`/`longitude` w formularzu dodawania/edycji stacji interaktywną mapą do kliknięcia lokalizacji.
- **Co wygenerował agent:** Komponent `LocationPickerMap.tsx` (Leaflet) oraz aktualizację `StationForm.tsx` i `index.css` (wybór dzielnicy automatycznie przesuwa pinezkę na mapie, kliknięcie ustawia dokładne współrzędne).
- **Zmiany właściciela:** Zaakceptował zmianę i poprosił o przygotowanie pliku `.env` pod `GEMINI_API_KEY`.

## Krok 17: Obsługa lokalnego pliku `.env` dla klucza Gemini API
- **O co poproszono:** Dodanie pliku `.env` i automatycznego wczytywania zmiennych z `.env` po stronie backendu.
- **Co wygenerował agent:** Moduł `backend/app/env.py` (standardowa biblioteka, bez dodatkowych zależności), wczytanie w `lifespan` w `main.py`, szablon `backend/.env.example`, lokalny `backend/.env` (ignorowany przez `.gitignore`), przekazanie `${GEMINI_API_KEY:-}` w `docker-compose.yml` oraz testy w `test_env.py`.
- **Zmiany właściciela:** Wkleił klucz do `.env`, przetestował w przeglądarce i zgłosił błąd `HTTP Error 404: Not Found` z Gemini API.

## Krok 18: Naprawa błędu 404 w integracji Gemini (fallback i odkrywanie modeli)
- **O co poproszono:** Naprawienie błędu `AI vision service failed: HTTP Error 404: Not Found` przy wywołaniu Gemini API.
- **Co wygenerował agent:** Aktualizację `services/ai_extractor.py` (przekazywanie klucza w nagłówku `x-goog-api-key` zamiast w URL, domyślny alias `gemini-flash-latest` z listą zapasową oraz automatyczne pobranie aktywnych modeli `flash` z `/v1beta/models` przy błędzie 404, plus czytelny komunikat błędu z odpowiedzi API) oraz test w `test_api_ai_extract.py`.
- **Zmiany właściciela:** Zgłosił timeout (`The read operation timed out`) mimo zużycia tokenów wejściowych na `Gemini 3.8 Flash`.

## Krok 19: Ograniczenie trybu thinking i wydłużenie timeoutu Gemini API
- **O co poproszono:** Wyeliminowanie timeoutu podczas odczytu zdjęcia przez domyślnie włączone rozumowanie (`thinking`) w modelu Gemini 3.8 Flash.
- **Co wygenerował agent:** Ustawienie `thinkingConfig` (`thinkingLevel: "MINIMAL"` dla Gemini 3.x/`flash-latest`, `thinkingBudget: 0` dla Gemini 2.5, z bezpiecznym fallbackiem bez `thinkingConfig` przy HTTP 400), `maxOutputTokens: 256`, timeout 60 s oraz pomijanie części `thought: true` przy parsowaniu odpowiedzi w `services/ai_extractor.py` + test w `test_api_ai_extract.py`.
- **Zmiany właściciela:** Oczekuje na ponowny test właściciela ze zdjęciem.

## Krok 20: Kolejność lżejszych modeli Flash i fallback po timeoutcie / błędzie sieciowym
- **O co poproszono:** Zapewnienie automatycznego przełączania na szybsze modele (`flash-lite`, `3.5-flash`) zamiast zatrzymywania się na timeoutcie `gemini-flash-latest`.
- **Co wygenerował agent:** Zmianę priorytetu modeli w `services/ai_extractor.py` (`gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-flash-latest`), timeout 20 s na pojedynczą próbę oraz automatyczne odkrywanie i przełączanie na kolejny model przy `TimeoutError` i błędach `404/429/5xx` + test `test_ai_extract_prices_gemini_falls_back_after_timeout`.
- **Zmiany właściciela:** Oczekuje na ponowny test właściciela ze zdjęciem.

## Krok 21: Masowe uzupełnianie cen ze zdjęcia i zaufanie dla odczytu Gemini AI (`source = "photo"`)
- **O co poproszono:** Po wrzuceniu zdjęcia aplikacja ma uzupełnić wszystkie odczytane paliwa w edytowalnych polach z zapisem jednym kliknięciem oraz traktować odczyt z prawdziwego Gemini AI (`mode === "gemini"`) jako zaufany, od razu aktualizując cenę na stacji do statusu `verified` (chyba że ktoś go później odrzuci).
- **Co wygenerował agent:** Rozszerzenie `PriceReport` (`models.py`), `database.py` (automatyczne dodanie kolumny `source` w istniejącym SQLite), `schemas.py` (`source: manual | photo`), `domain/consensus.py` (reguła zaufania dla nieodrzuconego raportu `photo`), testy w `test_domain_consensus.py` i `test_api_price_reports.py`, oraz panel zbiorczego przeglądu i zapisu wszystkich paliw ze zdjęcia w `NewPriceReportForm.tsx`, `StationForm.tsx`, `StationCard.tsx`, `App.tsx`, `api/client.ts` i `types/api.ts`.
- **Zmiany właściciela:** Zaakceptował zmianę kontraktu (warianty A1, A2, A3); oczekuje na weryfikację działania.

## Krok 22: Konto administratora na backendzie (`ADMIN_USERNAME` / `ADMIN_PASSWORD` + token HMAC)
- **O co poproszono:** Zablokowanie edycji/usuwania stacji i zarządzania rabatami dla zwykłego użytkownika (z pozostawieniem dodawania nowych stacji, cen i głosów) oraz dodanie konta admina konfigurowanego w `.env`.
- **Co wygenerował agent:** Czysty moduł `domain/auth.py` (weryfikacja poświadczeń `hmac.compare_digest`, podpisywane tokeny HMAC-SHA256 z czasem ważności), `services/admin.py`, `routers/admin.py` (`POST /admin/login`, `GET /admin/session`), zależność `require_admin` w `dependencies.py`, ochronę `PUT/DELETE /stations/{id}` i `POST/PUT/DELETE /benefits`, wpisy `ADMIN_USERNAME`/`ADMIN_PASSWORD` w `backend/.env` i `.env.example`, przekazanie w `docker-compose.yml` oraz testy `test_domain_auth.py` i `test_api_admin.py`.
- **Zmiany właściciela:** Oczekuje na potwierdzenie przed wdrożeniem UI logowania na frontendzie.

## Krok 23: Frontend logowania admina i ukrywanie akcji administracyjnych
- **O co poproszono:** Dodanie przycisku logowania administratora na frontendzie oraz ukrycie edycji/usuwania stacji i zarządzania rabatami przed zwykłymi użytkownikami.
- **Co wygenerował agent:** Komponent `AdminAuthBar.tsx` w nagłówku aplikacji, obsługę tokena Bearer (`sessionStorage`) i endpointów `/admin/login`, `/admin/session` w `api/client.ts` i `types/api.ts`, warunkowe wyświetlanie akcji `Edytuj`/`Usuń` w `StationCard.tsx` oraz CRUD-u rabatów w `BenefitsView.tsx` na podstawie `isAdmin` w `App.tsx`, plus style w `index.css`.
- **Zmiany właściciela:** Oczekuje na weryfikację w przeglądarce.

## Krok 24: Aktualizacja `README.md` o instalację, `.env` i nowe funkcje
- **O co poproszono:** Przygotowanie opisu instalacji i stanu projektu przed wysłaniem do repozytorium Git.
- **Co wygenerował agent:** Aktualizację `README.md` (instrukcja konfiguracji `backend/.env`, logowania admina, wyboru lokalizacji na mapie, odczytu AI ze zdjęć oraz aktualne endpointy i wymagane ograniczenia dema).
- **Zmiany właściciela:** Oczekuje na wskazanie docelowego repozytorium i wykonanie pierwszego commita / pusha.
