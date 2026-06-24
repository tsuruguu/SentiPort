#!/usr/bin/env bash
#
# Test end-to-end całego flow SentiPort: backend, baza, oraz REALNA
# łączność z agentami ElevenLabs (nie testy z mockami - prawdziwe
# wywołania HTTP do działającego backendu).
#
# Użycie:
#   chmod +x test_full_flow.sh
#   ./test_full_flow.sh
#
set -uo pipefail

BASE_URL="http://localhost:8000/api/v1"
ROOT_URL="http://localhost:8000"
PASS=0
FAIL=0

# --- Pomocnicze funkcje ---
green() { echo -e "\033[0;32m$1\033[0m"; }
red() { echo -e "\033[0;31m$1\033[0m"; }
yellow() { echo -e "\033[0;33m$1\033[0m"; }

check() {
    local description="$1"
    local actual_code="$2"
    local expected_code="$3"
    if [ "$actual_code" == "$expected_code" ]; then
        green "✓ $description (HTTP $actual_code)"
        PASS=$((PASS+1))
    else
        red "✗ $description (oczekiwano HTTP $expected_code, dostałem $actual_code)"
        FAIL=$((FAIL+1))
    fi
}

extract_json_field() {
    # $1 = plik z JSON-em, $2 = klucz (najwyższy poziom, lub items.0.klucz)
    python3 -c "
import json, sys
try:
    with open('$1') as f:
        data = json.load(f)
    path = '$2'.split('.')
    for p in path:
        if p.isdigit():
            data = data[int(p)]
        else:
            data = data[p]
    print(data)
except Exception:
    print('')
"
}

echo "=================================================="
echo " SentiPort - test end-to-end backendu"
echo "=================================================="
echo ""

# ---------------------------------------------------------------------
# 1. Backend żyje?
# ---------------------------------------------------------------------
echo "--- 1. Health check ---"
code=$(curl -s -o /tmp/sp_health.json -w "%{http_code}" "$ROOT_URL/health")
check "Backend odpowiada na /health" "$code" "200"
echo ""

# ---------------------------------------------------------------------
# 2. Czy dane testowe (seed) są w bazie?
# ---------------------------------------------------------------------
echo "--- 2. Lista nominacji (sprawdzenie seed danych) ---"
code=$(curl -s -o /tmp/sp_list.json -w "%{http_code}" "$BASE_URL/nominations/?limit=5")
check "GET /nominations/ zwraca 200" "$code" "200"

total=$(extract_json_field /tmp/sp_list.json "total")
if [ -n "$total" ] && [ "$total" -gt 0 ] 2>/dev/null; then
    green "✓ Baza ma dane: $total nominacji"
    PASS=$((PASS+1))
else
    red "✗ Baza wydaje się pusta (total=$total) - czy seed się wykonał? (docker-compose logs web)"
    FAIL=$((FAIL+1))
fi

NOMINATION_ID=$(extract_json_field /tmp/sp_list.json "items.0.nomination_id")
if [ -z "$NOMINATION_ID" ]; then
    red "✗ Nie udało się wyciągnąć nomination_id z listy - przerywam dalsze testy."
    echo ""
    echo "Surowa odpowiedź:"
    cat /tmp/sp_list.json
    exit 1
fi
yellow "  Używam nomination_id: $NOMINATION_ID"
echo ""

# ---------------------------------------------------------------------
# 3. Szczegóły nominacji
# ---------------------------------------------------------------------
echo "--- 3. Szczegóły nominacji ---"
code=$(curl -s -o /tmp/sp_detail.json -w "%{http_code}" "$BASE_URL/nominations/$NOMINATION_ID")
check "GET /nominations/{id} zwraca 200" "$code" "200"
echo ""

# ---------------------------------------------------------------------
# 4. EKSTRAKCJA - realne wywołanie agenta #1 (ElevenLabs)
# ---------------------------------------------------------------------
echo "--- 4. POST /extract (REALNE wywołanie agenta ekstrakcji) ---"
yellow "  To może potrwać do 60s - agent musi faktycznie odpowiedzieć..."
start_time=$(date +%s)
code=$(curl -s -o /tmp/sp_extract.json -w "%{http_code}" -X POST "$BASE_URL/nominations/$NOMINATION_ID/extract")
end_time=$(date +%s)
elapsed=$((end_time - start_time))

if [ "$code" == "200" ]; then
    green "✓ Agent ekstrakcji ODPOWIEDZIAŁ (${elapsed}s, HTTP $code)"
    PASS=$((PASS+1))
    status=$(extract_json_field /tmp/sp_extract.json "status")
    yellow "  Nowy status nominacji: $status"
elif [ "$code" == "422" ]; then
    red "✗ Agent ekstrakcji zwrócił błąd (422) - sprawdź ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID w .env"
    FAIL=$((FAIL+1))
    echo "  Szczegóły błędu:"
    cat /tmp/sp_extract.json
else
    red "✗ Nieoczekiwany kod HTTP: $code"
    FAIL=$((FAIL+1))
    cat /tmp/sp_extract.json
fi
echo ""

# ---------------------------------------------------------------------
# 5. WZBOGACENIE HISTORII - realne wywołanie agenta #2 (ElevenLabs)
# ---------------------------------------------------------------------
echo "--- 5. POST /enrich-with-history (REALNE wywołanie agenta wzbogacenia) ---"
yellow "  To może potrwać do 60s..."
start_time=$(date +%s)
code=$(curl -s -o /tmp/sp_enrich.json -w "%{http_code}" -X POST "$BASE_URL/nominations/$NOMINATION_ID/enrich-with-history")
end_time=$(date +%s)
elapsed=$((end_time - start_time))

if [ "$code" == "200" ]; then
    green "✓ Agent wzbogacenia ODPOWIEDZIAŁ (${elapsed}s, HTTP $code)"
    PASS=$((PASS+1))
elif [ "$code" == "422" ]; then
    red "✗ Agent wzbogacenia zwrócił błąd (422) - sprawdź ELEVENLABS_ENRICHMENT_AGENT_ID w .env"
    FAIL=$((FAIL+1))
    echo "  Szczegóły błędu:"
    cat /tmp/sp_enrich.json
else
    red "✗ Nieoczekiwany kod HTTP: $code"
    FAIL=$((FAIL+1))
    cat /tmp/sp_enrich.json
fi
echo ""

# ---------------------------------------------------------------------
# 6. TOP-3 nabrzeża (czysto lokalna logika, bez agenta)
# ---------------------------------------------------------------------
echo "--- 6. GET /recommended-berths (logika lokalna, bez agenta) ---"
code=$(curl -s -o /tmp/sp_berths.json -w "%{http_code}" "$BASE_URL/nominations/$NOMINATION_ID/recommended-berths")
check "GET /recommended-berths zwraca 200" "$code" "200"
echo ""

# ---------------------------------------------------------------------
# 7. Mailbox sync (test importu maili - opcjonalny, wymaga mailservera)
# ---------------------------------------------------------------------
echo "--- 7. POST /mailbox/sync-inbox (import z mailservera) ---"
code=$(curl -s -o /tmp/sp_mailbox.json -w "%{http_code}" -X POST "$BASE_URL/mailbox/sync-inbox" \
    -H "Content-Type: application/json" \
    -d '{"user":"agent@sentiport.pl","password":"haslo123"}')
check "POST /mailbox/sync-inbox zwraca 200" "$code" "200"
echo ""

# ---------------------------------------------------------------------
# Podsumowanie
# ---------------------------------------------------------------------
echo "=================================================="
echo " PODSUMOWANIE: $PASS zaliczone, $FAIL niezaliczone"
echo "=================================================="

if [ "$FAIL" -gt 0 ]; then
    echo ""
    yellow "Pliki z surowymi odpowiedziami zapisane w /tmp/sp_*.json - możesz je sprawdzić."
    exit 1
fi

exit 0