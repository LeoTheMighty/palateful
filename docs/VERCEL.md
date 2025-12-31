# Vercel Deployment Guide

This guide walks through deploying Palateful to Vercel with Vercel Postgres.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create Vercel Project](#create-vercel-project)
3. [Set Up Vercel Postgres](#set-up-vercel-postgres)
4. [Configure Environment Variables](#configure-environment-variables)
5. [Deploy](#deploy)
6. [Run Production Migrations](#run-production-migrations)
7. [Update Auth0 Configuration](#update-auth0-configuration)
8. [Custom Domain](#custom-domain)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

- Vercel account ([sign up free](https://vercel.com/))
- GitHub repository with your Palateful code
- Auth0 application configured (see [AUTH0.md](./AUTH0.md))
- Local development working

## Create Vercel Project

### Option 1: Import from GitHub

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **Add New... > Project**
3. Select **Import Git Repository**
4. Choose your Palateful repository
5. Click **Import**

Don't deploy yet - we need to configure environment variables first.

### Option 2: Using Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Link to Vercel
vercel link

# Follow prompts to create/link project
```

## Set Up Vercel Postgres

1. In your Vercel project, go to **Storage** tab
2. Click **Create Database**
3. Select **Postgres**
4. Choose a region close to your users
5. Click **Create**

After creation, Vercel automatically adds these environment variables:
- `POSTGRES_URL`
- `POSTGRES_PRISMA_URL`
- `POSTGRES_URL_NON_POOLING`
- And others...

### Configure DATABASE_URL

For Prisma, you need to set `DATABASE_URL` to use the Prisma-optimized URL:

1. Go to **Settings > Environment Variables**
2. Add a new variable:
   - Key: `DATABASE_URL`
   - Value: Copy from `POSTGRES_PRISMA_URL` in your Storage settings
3. Set it for all environments (Production, Preview, Development)

## Configure Environment Variables

In your Vercel project, go to **Settings > Environment Variables**.

Add the following variables for **Production** environment:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | (from Vercel Postgres) | Use POSTGRES_PRISMA_URL value |
| `AUTH0_SECRET` | (generate new) | Use `openssl rand -hex 32` |
| `AUTH0_BASE_URL` | `https://your-app.vercel.app` | Your Vercel URL |
| `AUTH0_ISSUER_BASE_URL` | `https://YOUR_AUTH0_DOMAIN` | Your Auth0 domain |
| `AUTH0_CLIENT_ID` | (from Auth0) | Same as local |
| `AUTH0_CLIENT_SECRET` | (from Auth0) | Same as local |
| `NODE_ENV` | `production` | |

> **Security Note**: Generate a NEW `AUTH0_SECRET` for production. Don't reuse your development secret.

### Generate Production AUTH0_SECRET

```bash
openssl rand -hex 32
```

## Deploy

### Automatic Deployment

If you imported from GitHub, Vercel automatically deploys on push to main.

Push your code:
```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### Manual Deployment

Using Vercel CLI:
```bash
vercel --prod
```

## Run Production Migrations

After your first deployment, you need to run migrations on the production database.

### Option 1: Using Vercel CLI

```bash
# Pull production environment variables
vercel env pull .env.production

# Run migrations with production database
DATABASE_URL="your-production-database-url" npx prisma migrate deploy
```

### Option 2: Using Vercel Dashboard

1. Go to your project's **Deployments** tab
2. Click on the latest deployment
3. Click **Functions** tab
4. Use the terminal to run: `npx prisma migrate deploy`

### Option 3: Add Migration to Build

Update `vercel.json`:
```json
{
  "buildCommand": "npx prisma migrate deploy && npx prisma generate && next build"
}
```

> **Note**: This runs migrations on every build, which may not be ideal for all workflows.

## Update Auth0 Configuration

After deployment, update Auth0 with your production URL.

In Auth0 Dashboard > Applications > Your Application > Settings:

### Application URIs

Add your Vercel URL (comma-separated with existing URLs):

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

Click **Save Changes**.

## Custom Domain

To add a custom domain:

1. Go to your Vercel project **Settings > Domains**
2. Enter your domain name
3. Follow the DNS configuration instructions
4. Wait for DNS propagation (can take up to 48 hours)

After adding a custom domain, update:
1. `AUTH0_BASE_URL` environment variable in Vercel
2. Auth0 Application URIs with your custom domain

## CI/CD with GitHub Actions

The project includes a GitHub Actions workflow that runs on every push:
- TypeScript type checking
- ESLint
- Build verification

Vercel handles the actual deployment automatically.

## Environment-Specific Settings

Vercel supports different environment variables for:
- **Production**: Main branch deployments
- **Preview**: Pull request deployments
- **Development**: Local development

This allows you to have separate Auth0 applications or databases for each environment if needed.

## Troubleshooting

### Build Fails: "Cannot find module '@prisma/client'"

**Solution:**
Ensure your `vercel.json` includes Prisma generation:
```json
{
  "buildCommand": "npx prisma generate && next build"
}
```

### Database Connection Error

**Solution:**
1. Verify `DATABASE_URL` is set correctly in Vercel
2. Use the `POSTGRES_PRISMA_URL` value (includes connection pooling)
3. Check that the database is in the same region as your deployment

### Auth0 Callback Error in Production

**Solution:**
1. Verify production URL in Auth0 Allowed Callback URLs
2. Check `AUTH0_BASE_URL` matches your Vercel URL exactly
3. Ensure no trailing slashes

### Migrations Not Applied

**Solution:**
Run migrations manually:
```bash
DATABASE_URL="your-production-url" npx prisma migrate deploy
```

### Preview Deployments Failing

**Solution:**
1. Set environment variables for "Preview" environment in Vercel
2. Consider using a separate preview database
3. Or use the same database with caution

### Cold Start Issues

Vercel Serverless Functions have cold starts. To minimize:
1. Use Vercel Postgres in the same region
2. Consider Vercel Edge Functions for auth routes
3. Enable "Always On" (paid feature)

## Monitoring

Vercel provides built-in monitoring:
- **Analytics**: View traffic and performance
- **Logs**: Real-time function logs
- **Speed Insights**: Core Web Vitals

Access these from your project dashboard.

## Cost Considerations

Vercel Free Tier includes:
- Unlimited deployments
- 100GB bandwidth
- Serverless function executions

Vercel Postgres Free Tier includes:
- 256MB storage
- 60 compute hours/month

For most personal projects, the free tier is sufficient.
