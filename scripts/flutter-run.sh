#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get ngrok URL from the API
NGROK_URL=$(curl --silent http://localhost:4040/api/tunnels 2>/dev/null | jq -r '.tunnels[0].public_url' 2>/dev/null)

if [ -z "$NGROK_URL" ] || [ "$NGROK_URL" == "null" ]; then
    echo -e "${RED}Could not detect ngrok URL.${NC}"
    echo -e "${YELLOW}Make sure docker compose is running: docker compose up -d${NC}"
    echo -e "${YELLOW}Or run: ./scripts/dev.sh${NC}"
    exit 1
fi

echo -e "${GREEN}Using API URL: $NGROK_URL${NC}"
echo ""

# Change to app directory and run flutter
cd "$(dirname "$0")/../app"

# Pass any additional arguments to flutter run
flutter run \
    --dart-define=API_BASE_URL="$NGROK_URL" \
    "$@"
