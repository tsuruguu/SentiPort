# SentiPort / DockWise — Frontend

React + JavaScript (bez TypeScript) + Vite + Tailwind CSS. Replikuje design
"DockWise" z mockupu PDF: Panel główny, Skrzynka, Dostawcy usług, Nadbrzeża.

## Uruchomienie

```bash
npm install
npm run dev
```

Otworzy się na `http://localhost:5173`.

## Konfiguracja backendu

Plik `.env` zawiera adres API:
```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

To jest domyślny adres backendu FastAPI z `docker-compose.yml`. Jeśli backend
działa pod innym adresem/portem, zmień tę wartość i zrestartuj `npm run dev`.

**Backend musi działać** (`docker-compose up -d --build` w `docker/`), żeby
frontend miał skąd brać dane - to nie jest aplikacja z danymi statycznymi.

## Struktura projektu

```
src/
├── api/                  # warstwa komunikacji z backendem
│   ├── client.js         # bazowy fetch wrapper + obsługa błędów
│   ├── nominations.js    # endpointy /nominations, /mailbox
│   ├── ports.js          # endpointy /ports, /ports/{id}/berths
│   └── documents.js      # endpointy /documents (generowanie PDF)
├── components/
│   ├── AppLayout.jsx     # wspólny layout (tło + nawigacja + outlet)
│   ├── TopNav.jsx        # górna nawigacja z logo, zakładkami, badge
│   ├── OceanBackground.jsx  # tło morskie (CSS/SVG, bez zewnętrznych zdjęć)
│   ├── GlassPanel.jsx    # biała szklana karta (reużywalna)
│   ├── ActionButton.jsx  # kolorowe przyciski akcji (zielony/niebieski/granatowy)
│   └── HighlightField.jsx   # żółte/różowe podświetlenie pól (dane od AI)
├── pages/
│   ├── DashboardPage.jsx     # Panel główny - "Sugestie AI" + dane portu
│   ├── InboxPage.jsx         # Skrzynka - lista maili/nominacji
│   ├── NominationDetailPage.jsx  # szczegóły jednej nominacji (klik z listy)
│   ├── BerthsPage.jsx        # Nadbrzeża - porty i ich nabrzeża
│   └── ProvidersPage.jsx     # Dostawcy usług (placeholder - backend jeszcze nie ma tej bazy)
├── hooks/
│   └── useApiData.js     # hook do pobierania danych z loading/error
├── utils/
│   └── format.js         # formatowanie dat, etykiety PL dla statusów/usług
├── App.jsx                # routing (react-router-dom)
├── main.jsx                # punkt wejścia
└── index.css               # Tailwind + fonty (Playfair Display + Inter)
```

## Uwaga: zakładka "Dostawcy usług"

Backend nie ma jeszcze modelu bazy dostawców usług (kontakty, dane
operacyjne) - to było oznaczone jako niezaimplementowane (RISK-006) w
dokumentacji wymagań. Strona pokazuje listę typów usług, które system już
rozpoznaje z maili, z jasnym komunikatem że pełna baza dostawców to kolejny
etap.

## Co dalej / czego nie zdążyłam dopracować

- Strona szczegółów nominacji (`/skrzynka/:id`) nie była jeszcze wizualnie
  weryfikowana - sprawdź czy wszystko się dobrze wyświetla
- Brak obsługi błędu "backend nie odpowiada" w bardziej przyjazny sposób niż
  goły komunikat z `ApiError`
- Brak stanu "ładowanie" w nawigacji przy przełączaniu zakładek (każda strona
  ładuje się od zera)
