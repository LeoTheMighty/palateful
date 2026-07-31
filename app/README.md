# palateful

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## nx integration

```bash
npx nx run app:test        # flutter test        (mirrors ci.yml flutter-test)
npx nx run app:analyze     # flutter analyze --no-fatal-warnings --no-fatal-infos
npx nx run app:build-web   # flutter build web --release  (mirrors ci.yml deploy-web)
```

**Why this was missing until 2026-07-30 (`debug/…-nxappproj`).** nx 22
discovers a project only from a `project.json` (or an nx-annotated
`package.json`) at its root — `nx.json` here registers no `plugins`, so there
is no inference at all. Every one of the 11 Python/infra projects has a
hand-written `project.json`; `app/` had only `pubspec.yaml`, which nx has no
reason to look at. Nothing was misconfigured — the file was simply never
written, and the gap stayed invisible because `services/e2e/project.json`
already drives Flutter indirectly with `cwd: {workspaceRoot}/app`.

Target commands are kept byte-identical to `devx.config.yaml →
projects[name=app]` (`test: flutter test`, path `app`) and to the `ci.yml`
steps, so the three callers cannot drift. `install` (`flutter pub get`) is
intentionally **not** a target: it would silently join
`npx nx run-many -t install`, which today means "install the Python
services".
