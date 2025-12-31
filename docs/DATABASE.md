# Database Setup Guide

This guide covers database setup and management for Palateful using Docker (local) and Vercel Postgres (production).

## Table of Contents

1. [Local Development with Docker](#local-development-with-docker)
2. [Prisma Commands](#prisma-commands)
3. [Database Schema](#database-schema)
4. [Prisma Studio](#prisma-studio)
5. [Production Database](#production-database)
6. [Migrations](#migrations)
7. [Troubleshooting](#troubleshooting)

## Local Development with Docker

### Start PostgreSQL

```bash
docker compose up -d
```

This starts PostgreSQL on `localhost:5432` with:
- **Database**: palate
- **User**: postgres
- **Password**: postgres

### Stop PostgreSQL

```bash
docker compose down
```

Data persists in a Docker volume.

### Reset Database (Delete All Data)

```bash
docker compose down -v  # -v removes volumes
docker compose up -d
npx prisma migrate dev  # Re-apply migrations
```

### View Logs

```bash
docker compose logs postgres
```

### Check Status

```bash
docker compose ps
```

## Prisma Commands

### Generate Client

After changing `schema.prisma`, regenerate the client:

```bash
npx prisma generate
```

### Create Migration

When you change the schema:

```bash
npx prisma migrate dev --name description_of_change
```

Example:
```bash
npx prisma migrate dev --name add_recipes_table
```

### Apply Migrations (Production)

In production, use:

```bash
npx prisma migrate deploy
```

This applies pending migrations without creating new ones.

### Reset Database (Development Only)

```bash
npx prisma migrate reset
```

> **Warning**: This deletes all data and re-applies migrations.

### View Migration Status

```bash
npx prisma migrate status
```

### Format Schema

```bash
npx prisma format
```

## Database Schema

### Current Schema

Located at `prisma/schema.prisma`:

```prisma
model User {
  id                     String   @id @default(cuid())
  auth0Id                String   @unique @map("auth0_id")
  email                  String   @unique
  name                   String?
  picture                String?
  emailVerified          Boolean  @default(false) @map("email_verified")
  hasCompletedOnboarding Boolean  @default(false) @map("has_completed_onboarding")
  createdAt              DateTime @default(now()) @map("created_at")
  updatedAt              DateTime @updatedAt @map("updated_at")

  @@map("users")
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique identifier (CUID) |
| `auth0Id` | String | Auth0 user ID (unique) |
| `email` | String | User's email address (unique) |
| `name` | String? | User's display name |
| `picture` | String? | Profile picture URL |
| `emailVerified` | Boolean | Whether email is verified |
| `hasCompletedOnboarding` | Boolean | Whether user completed welcome flow |
| `createdAt` | DateTime | Account creation timestamp |
| `updatedAt` | DateTime | Last update timestamp |

### Future Recipe Schema

When ready to add recipes, uncomment and migrate:

```prisma
model Recipe {
  id          String   @id @default(cuid())
  userId      String   @map("user_id")
  title       String
  description String?
  categories  String[] // ["Breakfast", "Lunch", "Dinner", "Dessert"]
  rating      Int?
  triedCount  Int      @default(0) @map("tried_count")
  createdAt   DateTime @default(now()) @map("created_at")
  updatedAt   DateTime @updatedAt @map("updated_at")

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId])
  @@map("recipes")
}
```

## Prisma Studio

Prisma Studio is a visual database browser.

### Launch Studio

```bash
npx prisma studio
```

Opens at http://localhost:5555

### Features

- View all tables and records
- Create, edit, delete records
- Filter and sort data
- View relations

### Use Cases

- Verify user creation after login
- Debug data issues
- Quick data inspection

## Production Database

### Vercel Postgres

For production, we use Vercel Postgres:

1. Create in Vercel Dashboard > Storage
2. Copy `POSTGRES_PRISMA_URL` to `DATABASE_URL`
3. Run migrations: `npx prisma migrate deploy`

### Connection String Format

```
postgresql://user:password@host:port/database?sslmode=require&pgbouncer=true
```

Important for Vercel Postgres:
- Always use connection pooling (`pgbouncer=true`)
- Enable SSL (`sslmode=require`)
- Use the Prisma-specific URL

### Running Production Migrations

```bash
# Set production DATABASE_URL
export DATABASE_URL="your-production-url"

# Apply migrations
npx prisma migrate deploy
```

Or use Vercel CLI:
```bash
vercel env pull .env.production
source .env.production
npx prisma migrate deploy
```

## Migrations

### Migration Files

Located at `prisma/migrations/`:

```
prisma/migrations/
├── 20231201000000_init/
│   └── migration.sql
└── migration_lock.toml
```

### Best Practices

1. **Always create migrations for schema changes**
   ```bash
   npx prisma migrate dev --name descriptive_name
   ```

2. **Review migration SQL before applying to production**
   ```bash
   cat prisma/migrations/*/migration.sql
   ```

3. **Test migrations locally first**
   ```bash
   npx prisma migrate reset  # Reset and re-apply all
   ```

4. **Never edit migration files after they're applied**

5. **Use `migrate deploy` in production, not `migrate dev`**

### Rolling Back

Prisma doesn't have built-in rollback. Options:

1. Create a new migration that undoes changes
2. Restore from database backup
3. In development: `npx prisma migrate reset`

## Troubleshooting

### "Can't reach database server"

**Causes:**
- Docker not running
- Wrong DATABASE_URL
- Port conflict

**Solution:**
```bash
# Check Docker
docker compose ps

# Restart PostgreSQL
docker compose restart

# Verify URL in .env
cat .env | grep DATABASE_URL
```

### "Migration failed"

**Causes:**
- Schema conflict
- Database state doesn't match migration history

**Solution:**
```bash
# Check migration status
npx prisma migrate status

# In development, reset and retry
npx prisma migrate reset
```

### "Prisma Client not generated"

**Cause:**
Client not regenerated after schema change

**Solution:**
```bash
npx prisma generate
```

### "Unique constraint violation"

**Cause:**
Trying to insert duplicate value for unique field

**Solution:**
Use `upsert` instead of `create`:
```typescript
await prisma.user.upsert({
  where: { email: 'user@example.com' },
  update: { name: 'Updated Name' },
  create: { email: 'user@example.com', name: 'New User' },
})
```

### Connection Pool Exhausted

**Cause:**
Too many database connections in serverless environment

**Solution:**
1. Use singleton Prisma client (already implemented in `src/lib/prisma.ts`)
2. Use connection pooling (Vercel Postgres includes this)
3. Reduce connection limit in DATABASE_URL:
   ```
   ?connection_limit=5
   ```

### Port 5432 Already in Use

**Cause:**
Another PostgreSQL instance running

**Solution:**
```bash
# Find what's using the port
lsof -i :5432

# Option 1: Stop the other service
brew services stop postgresql  # if using Homebrew

# Option 2: Change port in docker-compose.yml
ports:
  - '5433:5432'  # Use 5433 locally
```

Then update DATABASE_URL:
```
postgresql://postgres:postgres@localhost:5433/palate
```
