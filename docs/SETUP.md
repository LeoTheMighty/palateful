# Complete Setup Guide

This guide walks through the complete setup process for Palateful, from cloning the repository to running the application locally.

## Architecture Overview

Palateful is an NX monorepo with:
- **Backend**: Python FastAPI services (`services/api`, `services/worker`, `services/parser`)
- **Database**: PostgreSQL 16 with pgvector, managed by Alembic migrations (`services/migrator`)
- **Task Queue**: Celery + AWS SQS (LocalStack for local dev)
- **Mobile**: Flutter app (`app/`)
- **Infrastructure**: Docker Compose for local development

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js 20+** and **Yarn** — for NX monorepo tooling
  ```bash
  npm install -g yarn
  ```
- **Docker Desktop** — [Download here](https://www.docker.com/products/docker-desktop/) — runs all backend services
- **Flutter SDK 3.24+** — [Install guide](https://docs.flutter.dev/get-started/install)
- **Python 3.13+** and **Poetry** — only needed when editing Python services locally
  ```bash
  curl -sSL https://install.python-poetry.org | python3 -
  ```
- **Xcode 15+** (macOS, for iOS simulator) — install from Mac App Store
- **Android Studio** (for Android emulator) — [Download here](https://developer.android.com/studio)

You'll also need accounts for:
- **Auth0** — [Sign up free](https://auth0.com/) — handles user authentication
- **OpenAI** — [Sign up](https://platform.openai.com/) — AI recipe parsing and features
- **Firebase** — [Sign up free](https://firebase.google.com/) — push notifications (required for Story 6.3+)
- **AWS** account (or LocalStack for local dev — already included in Docker Compose)

## Step 1: Clone and Install

```bash
git clone <your-repo-url>
cd palateful
yarn install
```

This installs NX and build tooling. Python dependencies are managed per-service via Poetry and installed inside Docker images.

## Step 2: Configure Backend Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Database — used by API, worker, and migrator
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/palateful

# Redis — currently unused (commented out in docker-compose), reserve for future
REDIS_URL=redis://localhost:6379/0

# Auth0 — create an API in Auth0 dashboard and use its identifier as AUDIENCE
AUTH0_DOMAIN=auth.palateful.app
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
AUTH0_AUDIENCE=https://api.palateful.app

# OpenAI — for recipe import parsing
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# App
DEBUG=true
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]

# ngrok — for exposing local API to mobile device/simulator
NGROK_AUTHTOKEN=your-ngrok-authtoken
```

## Step 3: Configure Auth0

### Create Auth0 API

1. Go to [Auth0 Dashboard](https://manage.auth0.com/) → **Applications > APIs**
2. Click **Create API**
3. Set Name: "Palateful API", Identifier: `https://api.palateful.app`
4. Click **Create**

### Create Auth0 Native App (for Flutter)

1. Go to **Applications > Applications** → **Create Application**
2. Name: "Palateful Mobile", Type: **Native**
3. In Settings, set:
   - **Allowed Callback URLs**: `com.palateful.app://login-callback`
   - **Allowed Logout URLs**: `com.palateful.app://logout-callback`
4. Note the **Domain**, **Client ID** — you'll need these for the Flutter app

## Step 4: Start All Backend Services

```bash
docker compose up
```

This starts:
| Service | Port | Description |
|---------|------|-------------|
| `db` | 5432 | PostgreSQL 16 with pgvector |
| `migrator` | — | Runs Alembic migrations, then exits |
| `api` | 8000 | FastAPI REST API |
| `worker` | — | Celery task worker |
| `localstack` | 4566 | AWS SQS emulator for Celery broker |
| `ngrok` | 4040 | Public tunnel to API (for mobile) |

Migrations run automatically on every `docker compose up` via the `migrator` service.

> **Note:** The `parser` (OCR) service is in the `local-parser` profile and is **not started by default**. Start it only when needed:
> ```bash
> docker compose --profile local-parser up parser
> ```

Verify everything is running:
```bash
docker compose ps
```

API health check:
```bash
curl http://localhost:8000/health
```

## Step 5: Configure Flutter App

### Install Flutter Dependencies

```bash
cd app
flutter pub get
```

### Create App Environment File

```bash
cp app/.env.example app/.env
```

Edit `app/.env`:
```env
# For simulator (API running in Docker locally)
API_BASE_URL=http://localhost:8000

# For physical device (use ngrok URL — see Step 6)
# API_BASE_URL=https://abc123.ngrok.io

# Auth0 (use the Native app credentials from Step 3)
AUTH0_DOMAIN=auth.palateful.app
AUTH0_CLIENT_ID=your-native-client-id
AUTH0_AUDIENCE=https://api.palateful.app
```

### Configure iOS

1. Open the iOS project:
   ```bash
   open app/ios/Runner.xcworkspace
   ```
2. Select the **Runner** target → **Signing & Capabilities**
3. Select your **Team** (requires Apple Developer account for device builds)
4. Update **Bundle Identifier** (e.g., `com.yourcompany.palateful`)
5. Capabilities are already configured in `Info.plist` — review if bundle ID changes

### Configure Android

1. Update `app/android/app/build.gradle` with your `applicationId`
2. For release builds, create a signing key:
   ```bash
   keytool -genkey -v -keystore ~/upload-keystore.jks \
     -keyalg RSA -keysize 2048 -validity 10000 -alias upload
   ```

### Run the App

```bash
# iOS Simulator
cd app && flutter run -d ios

# Android Emulator
cd app && flutter run -d android

# List available devices
flutter devices
```

## Step 6: Mobile Testing with Physical Device (ngrok)

When testing on a physical device, the device can't reach `localhost`. ngrok creates a public tunnel automatically.

1. Get your ngrok authtoken from [ngrok dashboard](https://dashboard.ngrok.com/)
2. Add it to `.env`: `NGROK_AUTHTOKEN=your-token`
3. Start services: `docker compose up`
4. View the ngrok URL at: **http://localhost:4040** (ngrok web UI)
5. Update `app/.env`:
   ```env
   API_BASE_URL=https://abc123.ngrok-free.app
   ```
6. Rebuild and run the app on your device

## Step 7: Development Commands

```bash
# Build Docker images
npx nx run api:docker-build
npx nx run migrator:docker-build

# Start all services (primary dev workflow)
docker compose up

# Run Alembic migrations manually (requires DATABASE_URL set)
npx nx run migrator:migrate

# Install Python dependencies for a service
npx nx run api:install
npx nx run worker:install

# Run backend tests
npx nx run api:test

# Run backend linting
npx nx run api:lint

# Generate all lock files
npx nx run-many -t lock

# Flutter tests
cd app && flutter test
```

## Step 8: Configure Firebase (Push Notifications)

Firebase is used for push notifications in cooking mode timers and import job completion alerts.

> **Note:** Firebase is required for Story 6.3+ and 3.6+. The Flutter app already has `firebase_options.dart` configured. If starting fresh:

### Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **Add project** → name it "Palateful"
3. Add an **iOS app** with your bundle ID and an **Android app** with your applicationId
4. Download the config files:
   - iOS: `GoogleService-Info.plist` → place in `app/ios/Runner/`
   - Android: `google-services.json` → place in `app/android/app/`

### Configure FlutterFire

```bash
dart pub global activate flutterfire_cli
cd app
flutterfire configure --project=your-firebase-project-id
```

This regenerates `app/lib/firebase_options.dart`.

### Configure APNs (iOS Push Notifications)

1. Firebase Console → **Project Settings > Cloud Messaging**
2. Under "Apple app configuration", upload your APNs Authentication Key:
   - Get from [Apple Developer Portal](https://developer.apple.com/account/resources/authkeys/list) → Keys → create with APNs enabled
   - Download the `.p8` file, note Key ID and Team ID
3. Upload to Firebase with Key ID and Team ID

### Backend Firebase Credentials

Add to `.env`:
```env
# Path to Firebase service account JSON (do NOT commit this file)
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json

# OR inline JSON (for Docker/production)
FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'
```

## Step 9: Running Tests

### Backend Tests

```bash
# All API tests
npx nx run api:test

# Watch mode (requires pytest-watch)
docker compose exec api pytest --watch services/api/tests/
```

### Flutter Tests

```bash
cd app && flutter test
```

### Integration Tests (against live Docker stack)

```bash
# Start stack first
docker compose up -d

# Run integration tests
npx nx run api:test
```

## Common Issues

### Port 5432 Already in Use

```bash
# Find what's using it
lsof -i :5432
# Stop the conflicting service, or change the port in docker-compose.yml
```

### Docker Build Fails (Python Dependencies)

```bash
# Force rebuild without cache
docker compose build --no-cache api
docker compose up
```

### Migrations Failed

```bash
# Check migrator logs
docker compose logs migrator

# Manually run migrations
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/palateful \
  npx nx run migrator:migrate
```

### Flutter: Cannot Connect to API

1. Check Docker is running: `docker compose ps`
2. For simulator: ensure `API_BASE_URL=http://localhost:8000` in `app/.env`
3. For physical device: use ngrok URL (Step 6)
4. Check API is healthy: `curl http://localhost:8000/health`

### Auth0: Token Validation Fails

1. Verify `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` match exactly between `.env` and `app/.env`
2. The audience in `.env` must match the Auth0 API identifier created in Step 3
3. Check API logs: `docker compose logs api`

### ngrok: Tunnel Not Starting

1. Verify `NGROK_AUTHTOKEN` is set in `.env`
2. Check ngrok logs: `docker compose logs ngrok`
3. Free ngrok accounts allow 1 tunnel at a time — ensure no other tunnels are active

### LocalStack / SQS: Worker Not Processing Tasks

```bash
# Check LocalStack health
docker compose logs localstack

# Check worker logs
docker compose logs worker
```

## Project Structure

```
palateful/
├── services/
│   ├── api/          # FastAPI REST API (port 8000)
│   ├── worker/       # Celery async task worker
│   ├── parser/       # HunyuanOCR service (port 8001, local-parser profile)
│   └── migrator/     # Alembic database migrations
├── libraries/
│   └── utils/        # Shared Python models and business logic
├── app/              # Flutter mobile app
│   ├── lib/          # Dart source
│   └── test/         # Widget tests
├── terraform/        # AWS infrastructure (ECS, RDS, SQS, etc.)
├── docs/             # Project documentation
├── scripts/          # Utility and Docker init scripts
├── docker-compose.yml
├── .env.example
└── nx.json
```

## Next Steps

- [Recipe import system](./RECIPE_IMPORT_SYSTEM.md)
- [Recipe experience (cooking UI)](./RECIPE_EXPERIENCE_IMPLEMENTATION.md)
- [Shared shopping cart](./SHARED_SHOPPING_CART.md)
- [Deployment procedures](./DEPLOYMENT.md)
- Source of truth for the DB schema is the SQLAlchemy models in `services/api/src/db/models/`; for HTTP endpoints, see `services/api/src/routers/`.
