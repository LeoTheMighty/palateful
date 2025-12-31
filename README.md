# Palateful - Your Personal Recipe Book

A modern recipe management application built with Next.js, PostgreSQL, and Auth0.

## Tech Stack

- **Frontend**: Next.js 15+ (App Router), React 19, TypeScript 5.7, Tailwind CSS
- **Backend**: Next.js API Routes
- **Database**: PostgreSQL (Vercel Postgres for production, Docker for local)
- **ORM**: Prisma 7+
- **Authentication**: Auth0 (Google & Apple OAuth)
- **Deployment**: Vercel
- **Runtime**: Node.js 20 LTS

## Quick Start

### Prerequisites

- Node.js 20+ LTS
- Docker Desktop (for local PostgreSQL)
- Yarn package manager
- Auth0 account (free tier works)
- Vercel account (for deployment)

### Local Development Setup

1. **Clone and Install**
   ```bash
   git clone <your-repo-url>
   cd palate
   yarn install
   ```

2. **Setup Environment Variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and fill in your Auth0 credentials. See [Auth0 Setup Guide](./docs/AUTH0.md).

3. **Start PostgreSQL**
   ```bash
   docker compose up -d
   ```

4. **Run Database Migrations**
   ```bash
   npx prisma migrate dev
   npx prisma generate
   ```

5. **Start Development Server**
   ```bash
   yarn dev
   ```

6. **Open Application**
   Navigate to http://localhost:3000

## Detailed Setup Guides

- [Complete Setup Instructions](./docs/SETUP.md)
- [Auth0 Configuration](./docs/AUTH0.md)
- [Database Setup](./docs/DATABASE.md)
- [Vercel Deployment](./docs/VERCEL.md)

## Project Structure

```
palate/
├── .github/workflows/     # CI/CD pipeline
├── docs/                  # Documentation
├── prisma/                # Database schema and migrations
├── src/
│   ├── app/              # Next.js App Router pages
│   │   ├── api/          # API routes
│   │   ├── recipes/      # Recipe list page
│   │   └── welcome/      # Welcome/onboarding page
│   ├── components/       # React components
│   │   ├── auth/         # Auth-related components
│   │   ├── layout/       # Layout components
│   │   ├── recipes/      # Recipe-specific components
│   │   └── ui/           # Reusable UI components
│   ├── generated/        # Prisma generated client
│   └── lib/              # Utilities and configurations
├── .env.example          # Environment variables template
├── docker-compose.yml    # Local PostgreSQL setup
└── vercel.json           # Vercel configuration
```

## Available Scripts

| Command | Description |
|---------|-------------|
| `yarn dev` | Start development server |
| `yarn build` | Build for production |
| `yarn start` | Start production server |
| `yarn lint` | Run ESLint |
| `npx prisma studio` | Open Prisma Studio (database GUI) |
| `npx prisma migrate dev` | Create and apply new migration |
| `npx prisma generate` | Regenerate Prisma client |

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `AUTH0_SECRET` | Random string for session encryption | Yes |
| `AUTH0_BASE_URL` | Your app's base URL | Yes |
| `AUTH0_ISSUER_BASE_URL` | Your Auth0 domain URL | Yes |
| `AUTH0_CLIENT_ID` | Auth0 application client ID | Yes |
| `AUTH0_CLIENT_SECRET` | Auth0 application client secret | Yes |
| `NODE_ENV` | Environment (development/production) | Yes |

See `.env.example` for a complete template.

## Features

### Implemented
- [x] User authentication (Google & Apple OAuth via Auth0)
- [x] User profile management and database sync
- [x] Welcome/onboarding flow for new users
- [x] Recipe list view with category filters
- [x] Sort options (Surprise me, Best, Newest, etc.)
- [x] Empty state with add recipe button
- [x] Docker-based local development
- [x] CI/CD pipeline with GitHub Actions

### Coming Soon
- [ ] Recipe creation and editing
- [ ] Recipe import functionality
- [ ] Image upload for recipes
- [ ] Recipe sharing
- [ ] Meal planning

## Manual Setup Steps

After running the automated setup, you'll need to complete these manual steps:

### Auth0 Dashboard
1. Create a new "Regular Web Application"
2. Configure callback URLs (see [Auth0 Guide](./docs/AUTH0.md))
3. Enable Google and Apple OAuth providers
4. Copy credentials to your `.env` file

### Vercel Dashboard (for production)
1. Import your GitHub repository
2. Create a Postgres database in Storage tab
3. Add environment variables
4. Deploy and update Auth0 callback URLs

See the [detailed guides](./docs/) for step-by-step instructions.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add my feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Submit a pull request

## License

MIT
