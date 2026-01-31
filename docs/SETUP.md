# Complete Setup Guide

This guide walks through the complete setup process for Palateful, from cloning the repository to running the application locally.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js 20+** - [Download here](https://nodejs.org/)
- **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop/)
- **Yarn** - Install with `npm install -g yarn`
- **Git** - [Download here](https://git-scm.com/)
- **Flutter SDK 3.19+** - [Install guide](https://docs.flutter.dev/get-started/install)
- **Xcode 15+** (macOS only, for iOS) - Install from Mac App Store
- **Android Studio** (for Android) - [Download here](https://developer.android.com/studio)
- **Python 3.13+** - [Download here](https://www.python.org/downloads/)
- **Poetry** - Install with `curl -sSL https://install.python-poetry.org | python3 -`

You'll also need accounts for:
- **Auth0** - [Sign up free](https://auth0.com/)
- **Firebase** - [Sign up free](https://firebase.google.com/) (for push notifications)
- **OpenAI** - [Sign up](https://platform.openai.com/) (for AI recipe features)
- **Apple Developer Program** - [$99/year](https://developer.apple.com/programs/) (required for iOS App Store & push notifications)
- **Vercel** (for deployment) - [Sign up free](https://vercel.com/)

## Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd palate
```

## Step 2: Install Dependencies

```bash
yarn install
```

This installs all required npm packages including:
- Next.js and React
- Prisma ORM
- Auth0 SDK
- Tailwind CSS
- And other utilities

## Step 3: Configure Auth0

Before setting up environment variables, you need to create an Auth0 application.

1. Go to [Auth0 Dashboard](https://manage.auth0.com/)
2. Navigate to **Applications > Applications**
3. Click **Create Application**
4. Name it "Palateful" and select "Regular Web Applications"
5. Click **Create**

In the application settings, configure:

**Application URIs:**
- Allowed Callback URLs: `http://localhost:3000/api/auth/callback`
- Allowed Logout URLs: `http://localhost:3000`
- Allowed Web Origins: `http://localhost:3000`

Click **Save Changes**.

Now copy your credentials:
- Domain (e.g., `dev-xxxxx.us.auth0.com`)
- Client ID
- Client Secret

See [AUTH0.md](./AUTH0.md) for detailed Auth0 configuration including Google and Apple OAuth setup.

## Step 4: Set Up Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   ```env
   # Database
   DATABASE_URL="postgresql://postgres:postgres@localhost:5432/palate?schema=public"
   REDIS_URL="redis://localhost:6379"

   # Auth0
   AUTH0_DOMAIN="your-domain.us.auth0.com"
   AUTH0_CLIENT_ID="your-client-id"
   AUTH0_CLIENT_SECRET="your-client-secret"
   AUTH0_AUDIENCE="your-api-audience"

   # OpenAI (add after Step 6)
   OPENAI_API_KEY="sk-..."

   # Firebase (add after Step 5)
   FIREBASE_CREDENTIALS_PATH="/path/to/firebase-credentials.json"

   # Environment
   NODE_ENV="development"
   ```

## Step 5: Configure Firebase (Push Notifications)

Firebase Cloud Messaging (FCM) provides free unlimited push notifications for iOS and Android.

### Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **Add project**
3. Name it "Palateful" and follow the setup wizard
4. Once created, go to **Project Settings** (gear icon)

### Get Service Account Credentials (Backend)

1. In Project Settings, go to **Service Accounts** tab
2. Click **Generate new private key**
3. Save the JSON file securely (do NOT commit to git)
4. Set the environment variable:
   ```bash
   # Option 1: Path to the JSON file
   export FIREBASE_CREDENTIALS_PATH="/path/to/your/firebase-credentials.json"

   # Option 2: JSON content directly (useful for Docker/production)
   export FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'
   ```

### Configure iOS (APNs)

1. In Firebase Console, go to **Project Settings > Cloud Messaging**
2. Under "Apple app configuration", click **Upload** next to APNs Authentication Key
3. To get an APNs key:
   - Go to [Apple Developer Portal](https://developer.apple.com/account/resources/authkeys/list)
   - Click **Keys > +** to create a new key
   - Enable **Apple Push Notifications service (APNs)**
   - Download the `.p8` file (you can only download once!)
   - Note the **Key ID** and your **Team ID** (from Membership details)
4. Upload the `.p8` file to Firebase with the Key ID and Team ID

### Configure Flutter App

1. Install the FlutterFire CLI:
   ```bash
   dart pub global activate flutterfire_cli
   ```

2. Run the configuration command from the `app/` directory:
   ```bash
   cd app
   flutterfire configure --project=your-firebase-project-id
   ```

3. This generates `lib/firebase_options.dart` and platform-specific config files

### Add to Environment

Add to your `.env` file (or production environment):
```env
# Firebase - for push notifications
FIREBASE_CREDENTIALS_PATH="/path/to/firebase-credentials.json"
# OR
FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'
```

## Step 6: Configure OpenAI

OpenAI powers the AI recipe features including recipe parsing, ingredient extraction, and smart suggestions.

### Get API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign in or create an account
3. Navigate to **API Keys** in the left sidebar
4. Click **Create new secret key**
5. Name it "Palateful" and copy the key (you won't see it again!)

### Add to Environment

Add to your `.env` file:
```env
# OpenAI - for AI recipe features
OPENAI_API_KEY="sk-..."
```

### Pricing Note

OpenAI API is pay-per-use. For recipe parsing with `gpt-4o-mini`:
- ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- A typical recipe parse costs < $0.001
- Set usage limits in OpenAI dashboard to control costs

## Step 7: Set Up Flutter Mobile App

The Flutter app is located in the `app/` directory.

### Install Flutter Dependencies

```bash
cd app
flutter pub get
```

### Configure iOS

1. Open the iOS project in Xcode:
   ```bash
   open ios/Runner.xcworkspace
   ```

2. In Xcode, select the **Runner** target and go to **Signing & Capabilities**

3. Select your **Team** (requires Apple Developer account)

4. Update the **Bundle Identifier** to your unique identifier (e.g., `com.yourcompany.palateful`)

5. Enable required capabilities:
   - **Push Notifications** - Click "+ Capability" and add it
   - **Background Modes** - Enable "Remote notifications"

### Configure Android

1. Update `app/android/app/build.gradle`:
   - Set your `applicationId` (e.g., `com.yourcompany.palateful`)

2. For release builds, create a signing key:
   ```bash
   keytool -genkey -v -keystore ~/upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
   ```

3. Create `app/android/key.properties`:
   ```properties
   storePassword=<your-password>
   keyPassword=<your-password>
   keyAlias=upload
   storeFile=/Users/<you>/upload-keystore.jks
   ```

### Create App Environment File

Create `app/.env` with your API endpoint:
```env
API_BASE_URL=http://localhost:8000
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_AUDIENCE=your-api-audience
```

### Run the App

```bash
# iOS Simulator
flutter run -d ios

# Android Emulator
flutter run -d android

# List available devices
flutter devices
```

## Step 8: Start PostgreSQL

Start the local PostgreSQL database using Docker:

```bash
docker compose up -d
```

Verify it's running:
```bash
docker compose ps
```

You should see `palate-postgres` with status "Up".

## Step 9: Run Database Migrations

Apply the database schema:

```bash
npx prisma migrate dev
```

This creates the `users` table and generates the Prisma client.

If you make changes to `prisma/schema.prisma`, run:
```bash
npx prisma migrate dev --name description_of_change
npx prisma generate
```

## Step 10: Start the Development Server

```bash
yarn dev
```

The application will be available at http://localhost:3000

## Step 11: Test the Application

1. Open http://localhost:3000
2. You should see the Palateful landing page
3. Click "Sign In"
4. You'll be redirected to Auth0
5. Sign in with Google (or Apple if configured)
6. You'll be redirected back to the welcome page
7. Click "Let's Go" to complete onboarding
8. You should now see the empty recipe list

## Common Issues

### Port 5432 Already in Use

If you have another PostgreSQL instance running:

```bash
# Find what's using port 5432
lsof -i :5432

# Either stop that service, or change the port in docker-compose.yml
```

### Docker Not Running

Make sure Docker Desktop is running before starting PostgreSQL:

```bash
docker info
```

### Prisma Client Not Generated

If you see "Cannot find module '@/generated/prisma'":

```bash
npx prisma generate
```

### Auth0 Callback Error

If you get a callback URL mismatch error:
1. Check your Auth0 Application Settings
2. Ensure callback URLs exactly match (no trailing slashes)
3. Verify AUTH0_BASE_URL in `.env` matches

### Database Connection Failed

If Prisma can't connect to the database:
1. Ensure Docker is running: `docker compose ps`
2. Check DATABASE_URL format in `.env`
3. Try restarting PostgreSQL: `docker compose restart`

## Next Steps

- [Configure Google and Apple OAuth](./AUTH0.md)
- [Set up Vercel deployment](./VERCEL.md)
- [Learn about database management](./DATABASE.md)
