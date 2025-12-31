# Auth0 Configuration Guide

This guide walks through setting up Auth0 authentication for Palateful, including Google and Apple OAuth providers.

## Table of Contents

1. [Create Auth0 Application](#create-auth0-application)
2. [Configure Application Settings](#configure-application-settings)
3. [Set Up Google OAuth](#set-up-google-oauth)
4. [Set Up Apple OAuth](#set-up-apple-oauth)
5. [Configure Environment Variables](#configure-environment-variables)
6. [Test Authentication](#test-authentication)
7. [Production Configuration](#production-configuration)
8. [Troubleshooting](#troubleshooting)

## Create Auth0 Application

1. Go to [Auth0 Dashboard](https://manage.auth0.com/)
2. If you don't have an account, sign up for free
3. Navigate to **Applications > Applications**
4. Click **Create Application**
5. Configure:
   - **Name**: Palateful
   - **Application Type**: Regular Web Applications
6. Click **Create**

## Configure Application Settings

In your new application's settings:

### Basic Information

Note these values (you'll need them for `.env`):
- **Domain** (e.g., `dev-xxxxx.us.auth0.com`)
- **Client ID**
- **Client Secret** (click to reveal)

### Application URIs

Configure the following URLs:

**Allowed Callback URLs:**
```
http://localhost:3000/api/auth/callback
```

**Allowed Logout URLs:**
```
http://localhost:3000
```

**Allowed Web Origins:**
```
http://localhost:3000
```

> **Note**: When deploying to production, add your production URLs to each field (comma-separated).

Click **Save Changes** at the bottom of the page.

## Set Up Google OAuth

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services > OAuth consent screen**
4. Select **External** user type
5. Fill in required fields:
   - App name: Palateful
   - User support email: your email
   - Developer contact: your email
6. Click **Save and Continue**
7. Skip scopes for now, click **Save and Continue**
8. Add test users if needed, click **Save and Continue**

### Step 2: Create OAuth Credentials

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. Select **Web application**
4. Name: Palateful Auth0
5. Add **Authorized redirect URIs**:
   ```
   https://YOUR_AUTH0_DOMAIN/login/callback
   ```
   Replace `YOUR_AUTH0_DOMAIN` with your Auth0 domain (e.g., `dev-xxxxx.us.auth0.com`)
6. Click **Create**
7. Copy the **Client ID** and **Client Secret**

### Step 3: Configure in Auth0

1. In Auth0 Dashboard, go to **Authentication > Social**
2. Find **Google** and click it
3. Toggle **Enable** to ON
4. Enter your Google credentials:
   - Client ID
   - Client Secret
5. Click **Save**

## Set Up Apple OAuth

> **Note**: Apple OAuth requires an Apple Developer account ($99/year). You can skip this and use only Google OAuth if preferred.

### Step 1: Configure in Apple Developer Portal

1. Go to [Apple Developer](https://developer.apple.com/)
2. Navigate to **Certificates, Identifiers & Profiles**
3. Go to **Identifiers** and click **+**
4. Select **Services IDs** and click **Continue**
5. Configure:
   - Description: Palateful
   - Identifier: `com.yourcompany.palate.auth`
6. Click **Continue** then **Register**

### Step 2: Configure Sign in with Apple

1. Click on your new Service ID
2. Check **Sign In with Apple**
3. Click **Configure**
4. Configure:
   - Primary App ID: Select your app
   - Domains: `YOUR_AUTH0_DOMAIN`
   - Return URLs: `https://YOUR_AUTH0_DOMAIN/login/callback`
5. Click **Save**

### Step 3: Create Private Key

1. Go to **Keys** and click **+**
2. Name: Palateful Auth0
3. Check **Sign in with Apple**
4. Click **Configure** and select your Primary App ID
5. Click **Save** then **Continue** then **Register**
6. Download the key file (you can only do this once!)
7. Note the **Key ID**

### Step 4: Configure in Auth0

1. In Auth0 Dashboard, go to **Authentication > Social**
2. Find **Apple** and click it
3. Toggle **Enable** to ON
4. Enter your Apple credentials:
   - Team ID (found in Apple Developer account)
   - Key ID
   - Client ID (your Service ID identifier)
   - Client Secret Signing Key (contents of downloaded key file)
5. Click **Save**

## Configure Environment Variables

Update your `.env` file with Auth0 credentials:

```env
# Generate with: openssl rand -hex 32
AUTH0_SECRET="your-generated-secret"

# Your app's URL
AUTH0_BASE_URL="http://localhost:3000"

# Your Auth0 domain (include https://)
AUTH0_ISSUER_BASE_URL="https://dev-xxxxx.us.auth0.com"

# From Auth0 Application Settings
AUTH0_CLIENT_ID="your-client-id"
AUTH0_CLIENT_SECRET="your-client-secret"
```

Generate AUTH0_SECRET:
```bash
openssl rand -hex 32
```

## Test Authentication

1. Start your development server: `yarn dev`
2. Navigate to http://localhost:3000
3. Click **Sign In**
4. You should see Auth0's login page with Google (and Apple if configured)
5. Sign in with your preferred method
6. You should be redirected back to the welcome page

### Verify User Creation

After signing in, check that the user was created in your database:

```bash
npx prisma studio
```

Navigate to the Users table - you should see your new user record.

## Production Configuration

When deploying to production (e.g., Vercel):

### Update Auth0 URLs

Add your production URLs to Auth0 Application Settings:

**Allowed Callback URLs:**
```
http://localhost:3000/api/auth/callback,https://your-app.vercel.app/api/auth/callback
```

**Allowed Logout URLs:**
```
http://localhost:3000,https://your-app.vercel.app
```

**Allowed Web Origins:**
```
http://localhost:3000,https://your-app.vercel.app
```

### Update Environment Variables

In Vercel (or your hosting provider), set:
- `AUTH0_BASE_URL` = `https://your-app.vercel.app`
- Generate a new `AUTH0_SECRET` for production

### Update Google OAuth (if used)

In Google Cloud Console, add the production callback URL:
```
https://YOUR_AUTH0_DOMAIN/login/callback
```

## Troubleshooting

### "Callback URL mismatch"

This error means the callback URL doesn't match what's configured in Auth0.

**Solution:**
1. Check Auth0 Application Settings > Allowed Callback URLs
2. Ensure it exactly matches `http://localhost:3000/api/auth/callback`
3. No trailing slashes, case-sensitive
4. Click Save Changes

### "Invalid state"

This usually indicates a session issue.

**Solution:**
1. Clear browser cookies for localhost
2. Verify `AUTH0_SECRET` is set in `.env`
3. Restart the development server

### Social Login Not Appearing

If Google or Apple buttons don't appear on the login page:

**Solution:**
1. Verify the connection is enabled in Auth0 > Authentication > Social
2. Check that your application has access to the connection
3. In Auth0, go to your Application > Connections tab
4. Ensure the social connections are enabled for this application

### "Access Denied" from Google

**Solution:**
1. In Google Cloud Console, verify OAuth consent screen is configured
2. Add yourself as a test user if app is in testing mode
3. Check redirect URI matches exactly

### User Not Syncing to Database

If users can log in but don't appear in the database:

**Solution:**
1. Check the API route at `src/app/api/auth/[auth0]/route.ts`
2. Verify Prisma client is generated: `npx prisma generate`
3. Check database connection: `npx prisma studio`
4. Look for errors in the terminal

### Session Expires Too Quickly

**Solution:**
Session duration is configured in Auth0. To adjust:
1. Go to Auth0 Dashboard > Settings > Advanced
2. Adjust session lifetimes as needed
