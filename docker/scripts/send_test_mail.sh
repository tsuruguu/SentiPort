#!/usr/bin/env bash
#
# Skrypt do testowania mailservera SentiPort z linii komend.
# Wymaga zainstalowanego `swaks` (na Macu: brew install swaks).
#
# Użycie:
#   ./send_test_mail.sh armator1   -> wysyła testowy mail OD armator1 DO agenta
#   ./send_test_mail.sh agent      -> wysyła testowy mail OD agenta DO armator1
#
set -euo pipefail

DIRECTION="${1:-armator1}"
SMTP_HOST="localhost"
SMTP_PORT="587"

case "$DIRECTION" in
  armator1)
    FROM="armator1@armatorzy.pl"
    FROM_PASS="haslo123"
    TO="agent@sentiport.pl"
    SUBJECT="Nominacja - MV Test Vessel $(date +%H:%M:%S)"
    BODY="Dzień dobry,\n\nZgłaszamy nominację statku MV Test Vessel (IMO 9456789) do portu Gdynia (PLGDY).\nETA: $(date -v+2d '+%Y-%m-%d 10:00' 2>/dev/null || date -d '+2 days' '+%Y-%m-%d 10:00').\nŁadunek: kontenery mieszane, w tym reefer.\n\nZ poważaniem,\nArmator 1"
    ;;
  agent)
    FROM="agent@sentiport.pl"
    FROM_PASS="haslo123"
    TO="armator1@armatorzy.pl"
    SUBJECT="Potwierdzenie nominacji $(date +%H:%M:%S)"
    BODY="Dzień dobry,\n\nPotwierdzamy przyjęcie nominacji. Statek zostanie obsłużony na nabrzeżu wskazanym po analizie ryzyka.\n\nZ poważaniem,\nAgent SentiPort"
    ;;
  *)
    echo "Użycie: $0 [armator1|agent]"
    exit 1
    ;;
esac

swaks --to "$TO" \
      --from "$FROM" \
      --server "$SMTP_HOST" \
      --port "$SMTP_PORT" \
      --auth LOGIN \
      --auth-user "$FROM" \
      --auth-password "$FROM_PASS" \
      --tls \
      --header "Subject: $SUBJECT" \
      --body "$(printf "$BODY")"

echo ""
echo "Wysłano mail: $FROM -> $TO"
echo "Temat: $SUBJECT"