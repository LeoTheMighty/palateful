# Complete Setup Guide

This guide walks through the complete setup process for Palateful, from cloning the repository to running the application locally.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js 20+** - [Download here](https://nodejs.org/)
- **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop/)
- **Yarn** - Install with `npm install -g yarn`
- **Git** - [Download here](https://git-scm.com/)

You'll also need accounts for:
- **Auth0** - [Sign up free](https://auth0.com/)
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
   # Database - keep this as-is for local Docker setup
   DATABASE_URL="postgresql://postgres:postgres@localhost:5432/palate?schema=public"

   # Auth0 - fill in your credentials
   AUTH0_SECRET="<generate with: openssl rand -hex 32>"
   AUTH0_BASE_URL="http://localhost:3000"
   AUTH0_ISSUER_BASE_URL="https://YOUR_AUTH0_DOMAIN"
   AUTH0_CLIENT_ID="your-client-id"
   AUTH0_CLIENT_SECRET="your-client-secret"

   # Environment
   NODE_ENV="development"
   ```

3. Generate AUTH0_SECRET:
   ```bash
   openssl rand -hex 32
   ```
   Copy the output to AUTH0_SECRET in your `.env` file.

## Step 5: Start PostgreSQL

Start the local PostgreSQL database using Docker:

```bash
docker compose up -d
```

Verify it's running:
```bash
docker compose ps
```

You should see `palate-postgres` with status "Up".

## Step 6: Run Database Migrations

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

## Step 7: Start the Development Server

```bash
yarn dev
```

The application will be available at http://localhost:3000

## Step 8: Test the Application

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
