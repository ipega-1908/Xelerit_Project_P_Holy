# Gdzie Taniej? – Paliwo w Gdańsku (MVP)

Aplikacja webowa pomagająca kierowcom w Gdańsku porównać ceny paliw (ze słupka oraz po uwzględnieniu rabatów z aplikacji sieciowych) i obliczyć, czy objazd na tańszą stację rzeczywiście się opłaca.

## Główne funkcje

- **Społecznościowe zgłoszenia i weryfikacja cen:**
  - Każde zgłoszenie i korekta tworzą nowy, niezmienny rekord `PriceReport` (historia cen zostaje w bazie).
  - Jedno kliknięcie **✓** potwierdza cenę; **✕** otwiera formularz korekty, który atomowo (w jednej transakcji) zapisuje głos odrzucenia starego raportu i dodaje nowy raport z poprawną ceną.
  - Konsensus cenowy z okna 3 dni (`CONSENSUS_WINDOW_DAYS = 3`): obowiązuje cena z największym poparciem unikalnych użytkowników (zgłaszający + potwierdzający minus odrzucający), przy remisie wygrywa nowsze zgłoszenie.
  - Zgłoszenia ze zweryfikowanego zdjęcia Gemini AI (`source = "photo"`) od razu aktualizują obowiązującą cenę na stacji ze statusem `verified`, dopóki inni kierowcy nie zakwestionują ich korektą/odrzuceniem.
  - Test wiarygodności w okolicy: odchylenie o ponad `1,00 zł` od mediany co najmniej 3 innych stacji w promieniu 10 km oznacza cenę ręczną jako `suspicious` (podejrzana).
  - Wiek ceny i statusy: `verified`, `unconfirmed`, `suspicious`, `expired` (starsza niż 3 dni) oraz `unknown`.
- **Rabaty z aplikacji sieciowych (Benefits):**
  - Reguły rabatów (`Orlen Vitay`, `BPme`, `Circle K EXTRA`, `Shell ClubSmart`, `Super MOYA`) przechowywane są w bazie z datami `valid_from`, `valid_to` oraz `checked_at`.
  - Dni tygodnia i godziny obowiązywania liczone są w strefie `Europe/Warsaw` (`zoneinfo`), a rabat z limitem litrów (`max_liters`) naliczany jest wg wzoru `discount * min(liters, max_liters)`.
- **Kalkulator opłacalności objazdu (`GET /deals`):**
  - Punkt startu wybierany ręcznie z listy gdańskich dzielnic (domyślnie Śródmieście) lub kliknięciem bezpośrednio na interaktywnej mapie Leaflet (współrzędne nie są nigdzie zapisywane).
  - Odległość szacowana jako `haversine * 1.3`.
  - Porównanie z najbliższą stacją posiadającą cenę wybranego paliwa:
    - `detour_cost = extra_km * consumption_per_100km / 100 * price`
    - `savings = liters * (usual_price - cheaper_price)`
    - `net_gain = savings - detour_cost`
    - `min_liters = detour_cost / price_difference` (minimalna liczba litrów, od której objazd się opłaca)
- **Dodawanie stacji z mapy, masowy odczyt AI ze zdjęcia oraz panel admina:**
  - Każdy użytkownik może dodać nową stację wskazując jej lokalizację kliknięciem na mapie Leaflet, zgłaszać ceny oraz głosować (`✓` / `✕`).
  - Wrzucenie zdjęcia słupka/pylonu (`POST /ai/extract-prices`) uzupełnia wszystkie odczytane paliwa (`PB95`, `PB98`, `ON`, `LPG`) w edytowalnych polach z zapisem jednym kliknięciem. Bez klucza `GEMINI_API_KEY` działa deterministyczny tryb demo offline; z kluczem w `.env` backend korzysta z modeli Gemini Flash.
  - Edycja i usuwanie stacji oraz dodawanie/edycja/usuwanie rabatów wymagają zalogowania jako administrator (`POST /admin/login`, dane w `backend/.env`).

## Architektura

```
backend/
  app/
    domain/          # Czyste funkcje domenowe (zero zależności od FastAPI, SQLModel, DB i zegara)
    routers/         # Cienka warstwa HTTP (parsowanie żądań, wywołanie serwisu, odpowiedź)
    services/        # Logika aplikacyjna, sesje bazodanowe, integracja AI, autoryzacja admina
    models.py        # Tabele SQLModel (Station, PriceReport, PriceVote, Benefit)
    schemas.py       # Schematy Pydantic wejścia/wyjścia API
    database.py      # Konfiguracja SQLite (PRAGMA foreign_keys=ON)
    env.py           # Lekki loader zmiennych z lokalnego pliku .env
    seed.py          # 14 stacji w Gdańsku + przykładowe ceny i rabaty
    main.py          # Konfiguracja FastAPI, CORS, lifespan seed
  tests/             # Testy jednostkowe domeny + testy integracyjne API (SQLite in-memory)
frontend/
  src/
    api/             # Jeden typowany klient API (X-User-Id w localStorage, token admina w sessionStorage)
    components/      # Małe, wyspecjalizowane komponenty React (bez logiki biznesowej w JSX)
    constants/       # Dzielnice Gdańska, lista paliw i aplikacji
    hooks/           # Profil auta i aplikacji w localStorage
    types/           # Typy TypeScript (tryb strict, bez any)
    utils/           # Funkcje formatowania cen, wieku, rabatów i konwersji zdjęć
docs/
  AI_LOG.md          # Bieżący dziennik pracy z asystentem AI
```

## Dane startowe (Seed)

Przy pierwszym uruchomieniu backend automatycznie zasila bazę listą **14 stacji paliw z różnych dzielnic Gdańska** (Orlen, BP, Circle K, Shell, Moya, Auchan). **Wszystkie ceny paliw oraz rabaty w danych startowych są przykładowe** (służą wyłącznie do demonstracji kalkulatora i weryfikacji cen, nie są pobierane z zewnętrznych źródeł).

## Instalacja i uruchomienie lokalnie

### Wymagania
- Python 3.11+ oraz [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+ oraz `npm`

### 1. Konfiguracja `.env` (opcjonalnie AI + dane admina)
Skopiuj szablon i uzupełnij własne dane lokalnie (plik `.env` jest ignorowany przez Gita):

```bash
cp backend/.env.example backend/.env
```

Zmienne w `backend/.env`:
- `GEMINI_API_KEY` — opcjonalny klucz z Google AI Studio do prawdziwego odczytu cen ze zdjęć (gdy pusty, działa tryb demo offline).
- `ADMIN_USERNAME` i `ADMIN_PASSWORD` — login i hasło administratora odblokowujące w UI edycję/usuwanie stacji oraz zarządzanie rabatami.

### 2. Backend
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```
Dokumentacja OpenAPI będzie dostępna pod adresem `http://localhost:8000/docs`.

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
Aplikacja będzie dostępna pod adresem `http://localhost:5173`.

### 4. Testy i jakość kodu
```bash
# Backend: testy jednostkowe i API + linter i formatowanie
cd backend
uv run pytest -v
uv run ruff check .
uv run ruff format --check .

# Frontend: weryfikacja typów TypeScript i build produkcyjny
cd frontend
npm run typecheck
npm run build
```

### 5. Uruchomienie przez Docker (opcjonalne)
Przed startem możesz ustawić zmienne `GEMINI_API_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` w głównym pliku `.env` lub w środowisku powłoki, a następnie uruchomić:

```bash
docker compose up --build
```
Po zbudowaniu kontenerów frontend działa na `http://localhost:5173`, a backend na `http://localhost:8000`.

## Główne endpointy REST

- `GET/POST /stations`, `GET /stations/{id}`, `PUT/DELETE /stations/{id}` *(edycja/usuwanie: admin)*
- `GET/POST /stations/{id}/price-reports`
- `POST /price-reports/{id}/confirmations`
- `POST /price-reports/{id}/corrections`
- `GET /benefits`, `GET /benefits/{id}`, `POST/PUT/DELETE /benefits/{id}` *(zapis/usuwanie: admin)*
- `GET /deals?lat&lon&fuel&liters&consumption&apps`
- `POST /ai/extract-prices`
- `POST /admin/login`, `GET /admin/session`

Endpointy zapisujące zgłoszenia i głosy wymagają nagłówka `X-User-Id` (UUID generowanego w przeglądarce). Operacje administracyjne wymagają nagłówka `Authorization: Bearer <token>`.

## Ograniczenia demo i dalszy rozwój

- **Brak prawdziwej geolokalizacji:** punkt startu użytkownik wybiera ręcznie z listy dzielnic Gdańska lub kliknięciem na mapie Leaflet (bez użycia Geolocation API).
- **Brak kont kierowców (`X-User-Id`):** identyfikator `X-User-Id` generuje przeglądarka w `localStorage`, więc pojedynczy użytkownik może nadużywać głosowania po wyczyszczeniu pamięci przeglądarki; logowanie dotyczy wyłącznie prostego konta admina z `.env`.
- **Przykładowe dane:** ceny paliw oraz warunki rabatów z aplikacji sieci są przykładowe i nie aktualizują się automatycznie.
- **Uproszczony model odległości:** dystans liczony jest jako `haversine * 1,3`, a nie na podstawie rzeczywistej sieci drogowej i natężenia ruchu.
- **Stały próg odchylenia (1,00 zł):** próg oznaczania ceny jako podejrzanej nie skaluje się proporcjonalnie z poziomem cen (np. dla LPG jest relatywnie luźny w porównaniu do PB98).
- **Brak integracji z zewnętrznymi źródłami:** aplikacja nie pobiera ani nie scrapuje cen z oficjalnych serwisów stacji lub instytucji publicznych.

## Praca z AI

Projekt powstał iteracyjnie, w małych krokach kontrolowanych testami jednostkowymi i integracyjnymi. Szczegółowy zapis decyzji, kompromisów oraz podziału pracy znajduje się w [docs/AI_LOG.md](docs/AI_LOG.md).
