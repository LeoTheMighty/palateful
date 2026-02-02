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

# Parse arguments
PLATFORM=""
BUILD_MODE="--release"
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --debug)
            BUILD_MODE="--debug"
            shift
            ;;
        --release)
            BUILD_MODE="--release"
            shift
            ;;
        --profile)
            BUILD_MODE="--profile"
            shift
            ;;
        -d|--device-id)
            # User explicitly specified device, pass through
            EXTRA_ARGS+=("$1" "$2")
            PLATFORM="explicit"
            shift 2
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# Auto-detect device based on platform
if [ "$PLATFORM" == "explicit" ]; then
    # User specified device explicitly
    DEVICE_FLAG=()
elif [ "$PLATFORM" == "ios" ]; then
    DEVICE_ID=$(flutter devices 2>/dev/null | grep -i "• ios" | grep -v "simulator" | head -1 | sed -E 's/.*• ([A-Fa-f0-9-]+) •.*/\1/')
    if [ -n "$DEVICE_ID" ]; then
        echo -e "${GREEN}Auto-detected iOS device: $DEVICE_ID${NC}"
        DEVICE_FLAG=("-d" "$DEVICE_ID")
    else
        echo -e "${RED}No iOS device found. Make sure your iPhone is connected and trusted.${NC}"
        exit 1
    fi
elif [ "$PLATFORM" == "android" ]; then
    DEVICE_ID=$(flutter devices 2>/dev/null | grep -i "android" | head -1 | sed -E 's/.*• ([A-Za-z0-9:.-]+) •.*/\1/')
    if [ -n "$DEVICE_ID" ]; then
        echo -e "${GREEN}Auto-detected Android device: $DEVICE_ID${NC}"
        DEVICE_FLAG=("-d" "$DEVICE_ID")
    else
        echo -e "${RED}No Android device found.${NC}"
        exit 1
    fi
else
    DEVICE_FLAG=()
fi

echo ""
flutter run \
    $BUILD_MODE \
    --dart-define=API_BASE_URL="$NGROK_URL" \
    "${DEVICE_FLAG[@]}" \
    "${EXTRA_ARGS[@]}"
