# Palateful — Setup Guide

Complete reference for getting Palateful running: local development, production deployment, app store publishing, and third-party provider configuration across dev and prod environments.

---

## Table of Contents

1. [Security: Firebase Keys in Git](#security-firebase-keys-in-git)
2. [Prerequisites](#prerequisites)
3. [Third-Party Providers](#third-party-providers)
   - [Auth0](#auth0)
   - [Firebase / Google Cloud](#firebase--google-cloud)
   - [OpenAI](#openai)
   - [AWS](#aws)
   - [Ngrok](#ngrok)
   - [Apple Developer](#apple-developer)
   - [Google Play](#google-play)
4. [Local Development Setup](#local-development-setup)
5. [Production Deployment](#production-deployment)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [App Store Publishing](#app-store-publishing)
8. [Development Status](#development-status)

---

## Security: Firebase Keys in Git

**Action required before production use.**

Four Firebase configuration files are committed to the repo:

| File | Contains |
|------|----------|
| `app/lib/firebase_options.dart` | API keys for Android, iOS, Web |
| `app/android/app/google-services.json` | Android API key + project config |
| `app/ios/Runner/GoogleService-Info.plist` | iOS API key + project config |
| `app/firebase.json` | Firebase project config |

**Important context:** Firebase client-side API keys (`AIzaSy...`) are designed to be public. Google intentionally embeds them in distributed app binaries. They are project identifiers, not secrets. Security is enforced via Firebase Security Rules and App Check — not by keeping the key private.

**Actions to take:**

1. **Restrict the API keys** in Google Cloud Console → APIs & Services → Credentials. Restrict each `AIzaSy...` key to your app's bundle ID (`com.palateful.palateful`) and/or your production domain. This prevents quota abuse from unauthorized clients.

2. **Enable Firebase App Check** in Firebase Console to cryptographically bind requests to your app binaries.

3. **Optional rotation:** Delete Firebase app registrations, recreate them, re-run `flutterfire configure`. The new keys will still need to be committed — restriction + App Check is the real protection.

**What is correctly gitignored (NOT committed):**
- `.env` — Auth0 secret, OpenAI key, Ngrok token
- `secrets/firebase-credentials.json` — backend service account private key

If you shared the repo publicly before reviewing this, rotate your Auth0 client secret and OpenAI API key as a precaution.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker Desktop | Latest | All backend services locally |
| Node.js | 18+ | NX monorepo tooling |
| Yarn | 1.x | Node package manager (`npm i -g yarn`) |
| Flutter SDK | 3.9.0+ | Mobile and web frontend |
| Xcode | 15+ | iOS builds (macOS only) |
| Android Studio | Latest | Android builds + emulator |
| AWS CLI | v2 | Terraform and ECR operations |
| Terraform | 1.5+ | Infrastructure provisioning |
| FlutterFire CLI | Latest | Firebase Flutter config generation |

```bash
# Install FlutterFire CLI
dart pub global activate flutterfire_cli

# Install NX dependencies (from repo root)
yarn install
```

---

## Third-Party Providers

All providers need both a **dev** and a **prod** configuration. Keep them strictly separate — never point production traffic at dev credentials or vice versa.

---

### Auth0

Handles all authentication: Google Sign-In, Apple Sign-In, JWT issuance and validation.

#### Create two tenants

Create separate Auth0 tenants for dev and prod. Free plan covers dev; Pro plan recommended for prod (custom domains, higher rate limits).

| Setting | Dev | Prod |
|---------|-----|------|
| Tenant name | `palateful-dev` | `palateful` |
| Region | US | US (or closest to your users) |
| Domain | `palateful-dev.us.auth0.com` | `auth.palateful.app` (custom domain) |

#### Per-tenant configuration (repeat for each)

**1. Create an API**
- Name: `Palateful API`
- Identifier: `https://api.palateful.app` (same value in dev and prod — this is the JWT audience, not a real URL)
- Signing Algorithm: RS256

**2. Create a Native Application** (for the Flutter mobile app)
- Type: Native
- Name: `Palateful Mobile`
- Allowed Callback URLs (replace `YOUR_TENANT` with your actual Auth0 domain):
  ```
  com.palateful.app://auth.palateful.app/ios/com.palateful.palateful/callback,
  com.palateful.app://auth.palateful.app/android/com.palateful.palateful/callback
  ```
- Allowed Logout URLs:
  ```
  com.palateful.app://auth.palateful.app/ios/com.palateful.palateful/callback,
  com.palateful.app://auth.palateful.app/android/com.palateful.palateful/callback
  ```
- For web: add your web origin (e.g. `http://localhost:3000`, `https://app.palateful.app`)
- Note the **Client ID** (no secret needed for native apps)

**3. Create a Machine-to-Machine Application** (optional, for backend-initiated flows)
- Authorize it against the Palateful API

**4. Enable Social Connections**
- Google OAuth 2.0: requires a Google Cloud OAuth client (see Firebase section — same GCP project)
- Apple: requires Apple Developer account (see Apple Developer section below)
- Under Authentication → Social → Google: use your GCP OAuth credentials
- Under Authentication → Social → Apple: use your Apple Services ID

**5. Note your credentials**

| Variable | Where to find it |
|----------|-----------------|
| `AUTH0_DOMAIN` | Tenant domain (e.g. `auth.palateful.app`) |
| `AUTH0_CLIENT_ID` | Native Application → Settings → Client ID |
| `AUTH0_CLIENT_SECRET` | Native Application → Settings → Client Secret (backend only) |
| `AUTH0_AUDIENCE` | API → identifier (`https://api.palateful.app`) |

---

### Firebase / Google Cloud

Firebase is used for push notifications (FCM). The same GCP project also provides the Google OAuth credentials for Auth0 social login.

#### Create two Firebase projects

| Setting | Dev | Prod |
|---------|-----|------|
| Project name | `palateful-dev` | `palateful` |
| Project ID | `palateful-dev` | `palateful` |

#### Per-project setup

**1. Enable Firebase Cloud Messaging**
- Firebase Console → Project Settings → Cloud Messaging → Enable

**2. Register app platforms**

For each project, register three apps:
- Android: package name `com.palateful.palateful`
- iOS: bundle ID `com.palateful.palateful`
- Web: any nickname (e.g. "Palateful Web")

**3. Download platform config files**

Download and place in the repo (these files are committed and should be regenerated per-environment):

| File | Destination |
|------|-------------|
| `google-services.json` | `app/android/app/google-services.json` |
| `GoogleService-Info.plist` | `app/ios/Runner/GoogleService-Info.plist` |

Then regenerate `firebase_options.dart`:
```bash
cd app
flutterfire configure --project=palateful-dev   # for dev
flutterfire configure --project=palateful        # for prod
```

> For switching between environments, consider using `--out` to generate separate files (e.g. `firebase_options_dev.dart`, `firebase_options_prod.dart`) and import the appropriate one based on a build flavor. This is not currently set up — see Development Status.

**4. Create a service account for the backend**

Firebase Console → Project Settings → Service Accounts → Generate new private key.

Save as `secrets/firebase-credentials.json`. This directory is gitignored. Never commit this file.

**5. Set up Google OAuth for Auth0 social login**

In GCP Console → APIs & Services → Credentials → Create OAuth 2.0 Client ID:
- Application type: Web application
- Authorized redirect URIs: add your Auth0 callback, e.g.:
  `https://auth.palateful.app/login/callback`
- Copy the Client ID and Secret into Auth0 → Authentication → Social → Google

**6. Restrict Firebase API keys**

GCP Console → APIs & Services → Credentials → find each `AIzaSy...` key → Edit:
- Add Android app restriction: package name `com.palateful.palateful`
- Add iOS app restriction: bundle ID `com.palateful.palateful`
- Add website restriction for web key: your production domain

---

### OpenAI

Used for AI recipe features (gpt-4o-mini).

1. Create an account at platform.openai.com
2. Add a payment method and set a monthly spend limit
3. Generate an API key under API Keys
4. Create separate keys for dev and prod so you can track usage and revoke independently
5. Ensure your account has `gpt-4o-mini` access (available on all paid plans)

| Variable | Value |
|----------|-------|
| `OPENAI_API_KEY` | `sk-...` |
| `OPENAI_MODEL` | `gpt-4o-mini` |

---

### AWS

AWS is the production cloud provider. Not required for local development (LocalStack handles SQS locally).

#### Initial account setup

1. Create an AWS account (or use an existing one)
2. Enable MFA on the root account — do not use root credentials for anything else
3. Create an IAM user or role for Terraform with these policies:
   - `AdministratorAccess` (simplest for initial setup; lock down to least-privilege later)
4. Configure AWS CLI:
   ```bash
   aws configure
   # Provide Access Key ID, Secret Access Key, region: us-east-1
   ```
5. Create separate IAM users/roles for dev and prod environments, or use separate AWS accounts (recommended for strict isolation)

#### Terraform state backend (one-time)

Before first `terraform apply` for prod, create these manually:

```bash
# Create S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket palateful-terraform-state \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket palateful-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket palateful-terraform-state \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name palateful-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

#### Request GPU Spot quota increase

AWS Batch uses g4dn.xlarge and g5.xlarge Spot instances for OCR. Default Spot quota for GPU instances is 0.

1. Go to Service Quotas → Amazon EC2 → "Running On-Demand G and VT instances"
2. Request an increase to at least 8 vCPUs for dev, 32 for prod
3. This can take 1-3 business days to approve

Terraform will also attempt this via the quotas module, but manual requests are faster.

#### ECR repositories

The CI pipeline pushes images to ECR. Before first CI run, create the repositories:

```bash
# The Terraform ECR module creates the parser repo.
# The CI pipeline expects repos for api, migrator, and worker.
# These need to exist before CI can push:
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

for svc in api migrator worker; do
  aws ecr create-repository \
    --repository-name palateful-$svc \
    --image-scanning-configuration scanOnPush=true \
    --region us-east-1
done

echo "ECR base URL: $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com"
```

Note the ECR base URL — you'll need it for the `AWS_ECR_ACCOUNT_URL` GitHub secret.

---

### Ngrok

Used to expose your local API to a physical mobile device during development.

1. Create an account at ngrok.com
2. Get your authtoken from the ngrok dashboard
3. Add to `.env`:
   ```
   NGROK_AUTHTOKEN=your-token
   ```
4. When `docker compose up` runs, the ngrok service starts automatically and tunnels port 8000
5. Visit `http://localhost:4040` to see the live public URL
6. Update `app/.env` → `API_BASE_URL` to the ngrok URL when testing on a physical device

---

### Apple Developer

Required for: iOS builds, App Store submission, and Apple Sign-In in Auth0.

1. Enroll in the Apple Developer Program at developer.apple.com ($99/year)
2. Your account needs the **Account Holder** or **Admin** role to create the items below

#### App ID

1. Identifiers → App IDs → `+`
2. Bundle ID: `com.palateful.palateful`
3. Capabilities to enable:
   - Push Notifications
   - Sign In with Apple
   - Associated Domains (for universal links, if needed later)

#### Sign In with Apple (for Auth0)

1. Identifiers → Services IDs → `+`
2. Identifier: `com.palateful.palateful.siwa`
3. Enable "Sign In with Apple"
4. Configure: add your Auth0 domain as a Return URL:
   `https://auth.palateful.app/login/callback`
5. Copy this Services ID into Auth0 → Authentication → Social → Apple

#### Push Notification Certificate or Key

Firebase uses the APNs key (preferred over certificates):

1. Keys → `+` → Apple Push Notifications service (APNs)
2. Name: `Palateful APNs`
3. Download the `.p8` file — you only get one download
4. Note the Key ID and your Team ID (shown at top right of dev portal)
5. In Firebase Console → Project Settings → Cloud Messaging → iOS app → APNs Authentication Key: upload the `.p8` file with your Key ID and Team ID

#### Distribution Certificate

For App Store builds:

1. Certificates → `+` → Apple Distribution
2. Generate a CSR from Keychain Access on your Mac
3. Download and install the certificate in Keychain Access

#### Provisioning Profile

1. Profiles → `+` → App Store Connect → App Store
2. Select the `com.palateful.palateful` App ID
3. Select your Distribution Certificate
4. Download and install in Xcode

#### App Store Connect

1. Go to appstoreconnect.apple.com
2. Apps → `+` → New App
3. Platform: iOS, Bundle ID: `com.palateful.palateful`
4. Fill in name, primary language, SKU
5. Create the app record before your first build submission

---

### Google Play

Required for Android app distribution.

1. Create a Google Play Developer account at play.google.com/console ($25 one-time)
2. Complete the developer profile and accept the Distribution Agreement

#### Create the app

1. All apps → Create app
2. App name: Palateful
3. Default language: English
4. App or game: App
5. Free or paid: (your choice)

#### Android signing keystore

Unlike iOS, you generate and control the Android signing key:

```bash
keytool -genkey -v \
  -keystore palateful-release.jks \
  -alias palateful \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000
```

Store this `.jks` file securely — losing it means you can never update the app on Play. Back it up to a password manager or secure storage.

Configure signing in `app/android/app/build.gradle.kts`:

```kotlin
android {
    signingConfigs {
        create("release") {
            keyAlias = System.getenv("KEY_ALIAS") ?: "palateful"
            keyPassword = System.getenv("KEY_PASSWORD") ?: ""
            storeFile = file(System.getenv("KEYSTORE_PATH") ?: "palateful-release.jks")
            storePassword = System.getenv("STORE_PASSWORD") ?: ""
        }
    }
    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}
```

Store these env vars (`KEY_ALIAS`, `KEY_PASSWORD`, `KEYSTORE_PATH`, `STORE_PASSWORD`) in your CI secrets.

#### Google Play App Signing (recommended)

Enroll in Google Play App Signing so Google holds the final distribution key. You sign the upload AAB with your upload key; Google re-signs the final APK. This protects you if you lose your keystore.

1. Upload your first AAB to Play Console
2. Follow the App Signing enrollment flow
3. Download the upload certificate and keep it for CI

---

## Local Development Setup

### 1. Clone and install

```bash
git clone <repo>
cd palateful
yarn install
```

### 2. Configure backend environment

```bash
cp .env.example .env
```

Fill in `.env`:

```bash
# Database (no change needed for local Docker)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/palateful
REDIS_URL=redis://localhost:6379/0

# Auth0 — use your dev tenant values
AUTH0_DOMAIN=auth.palateful.app
AUTH0_CLIENT_ID=<native-app-client-id>
AUTH0_CLIENT_SECRET=<native-app-client-secret>
AUTH0_AUDIENCE=https://api.palateful.app

# OpenAI — dev API key
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# App
DEBUG=true
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]

# Ngrok
NGROK_AUTHTOKEN=<your-ngrok-token>

# Firebase (backend service account)
FIREBASE_CREDENTIALS_PATH=./secrets/firebase-credentials.json

# AWS parser (only needed if using OCR locally)
AWS_REGION=us-east-1
PARSER_INPUTS_BUCKET=palateful-parser-inputs-dev
PARSER_OUTPUTS_BUCKET=palateful-parser-outputs-dev
BATCH_JOB_QUEUE=palateful-parser-queue-dev
BATCH_JOB_DEFINITION=palateful-parser-job-dev
```

### 3. Configure Flutter environment

```bash
cp app/.env.example app/.env
```

Fill in `app/.env`:

```bash
API_BASE_URL=http://localhost:8000
AUTH0_DOMAIN=auth.palateful.app
AUTH0_CLIENT_ID=<native-app-client-id>
AUTH0_AUDIENCE=https://api.palateful.app
```

For testing on a physical device, replace `localhost:8000` with your ngrok URL from `http://localhost:4040`.

### 4. Place Firebase service account

```bash
mkdir -p secrets
cp ~/Downloads/palateful-dev-firebase-adminsdk-*.json secrets/firebase-credentials.json
```

### 5. Start backend services

```bash
docker compose up
```

Starts: PostgreSQL (5432), API (8000), Worker (Celery/SQS), LocalStack SQS (4566), Ngrok (4040).

### 6. Run migrations

```bash
docker compose --profile migrate up migrator
```

### 7. Run the Flutter app

```bash
cd app
flutter pub get
flutter run              # auto-selects connected device
flutter run -d chrome    # web
flutter run -d ios       # iOS Simulator
flutter run -d emulator  # Android Emulator
```

### 8. Verify everything

| Check | URL |
|-------|-----|
| API health | http://localhost:8000/health |
| API docs (Swagger) | http://localhost:8000/docs |
| Ngrok tunnel URL | http://localhost:4040 |
| LocalStack SQS | http://localhost:4566 |

### Optional: Run OCR parser locally (CPU only)

```bash
docker compose --profile local-parser up parser
# Parser available at http://localhost:8001
```

---

## Production Deployment

### 1. Configure production environment secrets

Production secrets live in your CI/CD system (GitHub Actions), not in files. See [CI/CD Pipeline](#cicd-pipeline) for the full secrets list.

For manual deploys or one-off operations, you can use a `.env.prod` file (gitignored) with the same structure as `.env` but pointing to production resources.

### 2. Provision infrastructure with Terraform

```bash
cd terraform

# Initialize with prod S3 backend
terraform init -reconfigure -backend-config=backend-prod.hcl

# Review the plan
terraform plan -var-file=production.tfvars

# Apply
terraform apply -var-file=production.tfvars
```

This creates:
- VPC with public subnets
- S3 buckets for parser I/O
- ECR repository for parser image
- IAM roles (Batch instance, job, service, Spot fleet)
- AWS Batch compute environment (Spot GPU: g4dn.xlarge, g5.xlarge)
- Batch job queue and job definition
- Service Quotas increase request for Spot GPU instances
- CloudWatch log groups

**Note:** ECS, RDS, API Gateway, Lambda, ElastiCache, and Redis modules exist in `terraform/modules/` but are not yet wired into the environment configs. These need to be added to `terraform/environments/prod/main.tf` before full production deployment.

### 3. Build and push Docker images

```bash
# Log in to ECR
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push API
npx nx run api:docker-build
docker tag palateful-api:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/palateful-api:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/palateful-api:latest

# Same for migrator and worker
```

The CI pipeline does this automatically on every push to `main` (tagged with commit SHA).

### 4. Build and push parser batch image

The parser uses a separate GPU Dockerfile for Batch:

```bash
# Build multi-arch (required for AWS Batch linux/amd64)
docker buildx build \
  --platform linux/amd64 \
  -f services/parser/Dockerfile.batch \
  -t $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/palateful-parser:latest \
  --push \
  services/parser/
```

This image pre-bakes the HunyuanOCR model weights (~3-5 min build time) to avoid cold-start downloads on every Batch job.

### 5. Run production migrations

```bash
# Set DATABASE_URL to your RDS endpoint, then:
DATABASE_URL=postgresql://user:pass@your-rds-endpoint:5432/palateful \
  npx nx run migrator:migrate
```

Or trigger the migrator ECS task via the AWS Console / CLI once ECS is configured.

### 6. Production environment variables

These go into ECS task definitions (or AWS Secrets Manager, injected at runtime):

```bash
# Database
DATABASE_URL=postgresql://user:pass@rds-endpoint:5432/palateful

# Redis (ElastiCache)
REDIS_URL=redis://elasticache-endpoint:6379/0

# Auth0 — PROD tenant (custom domain)
AUTH0_DOMAIN=auth.palateful.app
AUTH0_CLIENT_ID=<prod-client-id>
AUTH0_CLIENT_SECRET=<prod-client-secret>
AUTH0_AUDIENCE=https://api.palateful.app

# OpenAI — separate prod key
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# App
DEBUG=false
CORS_ORIGINS=["https://app.palateful.app"]
ENVIRONMENT=production

# AWS
AWS_REGION=us-east-1
PARSER_INPUTS_BUCKET=palateful-parser-inputs-prod
PARSER_OUTPUTS_BUCKET=palateful-parser-outputs-prod
BATCH_JOB_QUEUE=palateful-parser-queue-prod
BATCH_JOB_DEFINITION=palateful-parser-job-prod

# Firebase
FIREBASE_CREDENTIALS_PATH=/run/secrets/firebase-credentials.json
```

---

## CI/CD Pipeline

The pipeline is defined in `.github/workflows/ci.yml`. It runs lint, tests, model checks, Flutter analysis, Terraform validation, and image builds on every push and PR.

### GitHub Secrets required

Add these under repo Settings → Secrets and variables → Actions:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user key for ECR push |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret for ECR push |
| `AWS_ECR_ACCOUNT_URL` | ECR base URL, e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com` |
| `AWS_REGION` | `us-east-1` |

### What the pipeline does

| Job | Trigger | What it does |
|-----|---------|--------------|
| `setup` | PR + push | Installs Python 3.13, Node 22, Poetry; caches workspace |
| `lint` | PR + push | `npx nx affected -t lint` |
| `test` | PR + push | Runs migrations against a test PG container, then `npx nx affected -t test` |
| `check-models` | PR + push | Verifies SQLAlchemy models match Alembic migrations |
| `flutter-test` | All branches | `flutter analyze` + `flutter test` |
| `terraform` | PR + push | `terraform fmt` check, `init`, `validate`, `plan` (no apply) |
| `deploy-images` | Push to `main` | Builds and pushes api, migrator, worker images to ECR (tagged with commit SHA) |

### Enabling Terraform auto-apply (not yet active)

The `terraform apply` step is commented out pending S3 backend activation. Once the state bucket exists:

1. Uncomment the apply step in `.github/workflows/ci.yml`
2. Add a GitHub Environment called `production` with a required reviewer for approval before apply

---

## App Store Publishing

### iOS — Apple App Store

#### Build

```bash
cd app

# Get dependencies
flutter pub get

# Build release IPA
flutter build ipa --release

# Output: build/ios/ipa/palateful.ipa
```

For CI, use:
```bash
flutter build ipa --release --export-options-plist=ios/ExportOptions.plist
```

You'll need to create `app/ios/ExportOptions.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>app-store-connect</string>
    <key>teamID</key>
    <string>YOUR_TEAM_ID</string>
    <key>uploadSymbols</key>
    <true/>
    <key>compileBitcode</key>
    <false/>
</dict>
</plist>
```

#### Submit

```bash
# Upload to App Store Connect (requires xcrun altool or Transporter)
xcrun altool --upload-app \
  --type ios \
  --file build/ios/ipa/palateful.ipa \
  --apiKey YOUR_APP_STORE_CONNECT_API_KEY \
  --apiIssuer YOUR_ISSUER_ID
```

Or drag the `.ipa` into Transporter.app.

#### App Store Connect checklist

- [ ] App icon (1024×1024 PNG, no alpha)
- [ ] Screenshots for all required device sizes (6.7", 6.5", 5.5" iPhone; optional iPad)
- [ ] App description, keywords, subtitle
- [ ] Privacy policy URL (required)
- [ ] Age rating questionnaire
- [ ] Export compliance (encryption question — Auth0 uses HTTPS/TLS, answer yes to standard encryption exemption)
- [ ] TestFlight beta testing before submission

---

### Android — Google Play

#### Build

```bash
cd app

# Get dependencies
flutter pub get

# Build release AAB (preferred over APK for Play)
flutter build appbundle --release

# Output: build/app/outputs/bundle/release/app-release.aab
```

Signing happens via the keystore config added in `build.gradle.kts` (see Google Play section above). Pass credentials via env vars:

```bash
KEY_ALIAS=palateful \
KEY_PASSWORD=your-key-password \
KEYSTORE_PATH=/path/to/palateful-release.jks \
STORE_PASSWORD=your-store-password \
flutter build appbundle --release
```

#### Submit

1. Open Google Play Console → your app → Production → Create new release
2. Upload `app-release.aab`
3. Add release notes
4. Roll out (can start at 10-20% for staged rollout)

#### Play Store checklist

- [ ] App icon (512×512 PNG)
- [ ] Feature graphic (1024×500 PNG)
- [ ] Screenshots for phone and 7" tablet
- [ ] Short and full description
- [ ] Privacy policy URL
- [ ] Content rating questionnaire
- [ ] Data safety form (declare what data is collected: email, usage data, etc.)
- [ ] Declare whether app uses advertising ID
- [ ] Internal testing → Closed testing → Open testing → Production (staged rollout)

---

## Development Status

### Completed

| Epic | Stories done |
|------|-------------|
| 1 – Foundation | App shell, sign-in, user profile (1.1–1.3) |
| 2 – Recipe Management | Full CRUD, recipe books, photos, favorites, archive, bulk ops (2.1–2.8) |
| 3 – Import Pipeline | URL import, OCR, CSV bulk, exception queue, share sheet, push notifications (3.1–3.6) |
| 4 – Versioning & Notes | Auto-versioning, history, restore, recipe notes (4.1–4.4) |
| 5 – Search | Fuzzy/semantic search, filters, home screen, archive view (5.1–5.5) |
| 6 – Cooking Mode | Core experience, gesture nav, timers, offline mode, post-cook feedback (6.1–6.5) |
| 7 – Collaboration | Shared recipe books, invitations, forking, real-time updates, activity notifications (7.1–7.5) |
| 8 – Shopping Lists | Shared real-time list, add from recipe, check-off sync (8.1–8.3) |
| 9 – Meal Planning | Schedule, browse, add to shopping list, aggregate by date range (9.1–9.4) |

### In review

| Story | Description |
|-------|-------------|
| 1.4 | Onboarding flow |
| 1.5 | Empty states with contextual prompts |
| 1.6 | CI/CD pipeline setup |
| 10.1 | Export recipe collection |

### Remaining (backlog)

| Story | Description | Notes |
|-------|-------------|-------|
| 10.2 | Share recipe via public link | Backend + Flutter |
| 10.3 | Native platform sharing (iOS/Android share sheet) | Flutter only |
| 10.4 | Flutter web with responsive layout | Flutter only |
| 10.5 | Mobile app store builds | Release config, signing, store setup |
| 11.1 | AI chat with tool calling | Backend + Flutter |
| 11.2 | AI recipe search | Backend + Flutter |
| 11.3 | AI adds notes to recipes | Backend + Flutter |
| 11.4 | AI recipe suggestions | Backend + Flutter |
| 11.5 | AI in cooking mode (Q&A) | Backend + Flutter |
| 11.6 | Hands-free voice input in cooking mode | Flutter + platform APIs |

### Infrastructure gaps before production

These Terraform modules exist but are not yet wired into environment configs:

| Module | What it does | Status |
|--------|-------------|--------|
| `modules/ecs` | ECS Fargate for API and worker | Exists, not connected |
| `modules/rds` | RDS PostgreSQL 16 | Exists, not connected |
| `modules/api-gateway` | API Gateway + Lambda JWT authorizer | Exists, not connected |
| `modules/elasticache` | Redis | Exists, not connected |

These need to be added to `terraform/environments/prod/main.tf` before a production deployment can run.

---

## Key Ports (local)

| Port | Service |
|------|---------|
| 8000 | FastAPI API |
| 8001 | Parser service (profile: `local-parser`) |
| 5432 | PostgreSQL |
| 6379 | Redis (if enabled) |
| 4566 | LocalStack (SQS) |
| 4040 | Ngrok dashboard |
