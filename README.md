# Breidablik

A household/collective manager: rotating chores (duties), one-off tasks, a shared event
calendar, and shopping lists — with web push notifications and calendar app subscriptions.
Installable as a PWA, mobile-first.

## Stack

- **Backend**: FastAPI (JSON API only), SQLAlchemy 2.0 (async) + PostgreSQL, Alembic migrations,
  `fastapi-users` for auth (cookie session + TOTP 2FA + a device-PIN quick-login on top),
  `pywebpush` for Web Push, `icalendar` for the calendar subscription feed.
- **Frontend**: Nuxt 3 in static-SPA mode (`ssr: false`, Nitro `static` preset) — it compiles to
  plain static files with no Node server involved at runtime, in Docker or on shared hosting.
- **Deployment**: a single FastAPI process serves both the JSON API and the built frontend.
  Works identically as a Docker container or under Phusion Passenger.

## Local development

Requires Python 3.11+, Node 22+, and a PostgreSQL instance (the quickest way to get one is
`docker compose up -d db`, which also works fine while running the app itself outside Docker).

```bash
# Backend
uv venv
uv pip install -e ".[dev]"
cp .env.example .env          # then fill in SECRET_KEY, VAPID_*, etc. — see below
alembic upgrade head

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                    # dev server on :3000, proxies /api to :8000

# Backend dev server
uvicorn app.main:app --reload --port 8000
```

Create the first account (registration is intentionally not public — see Auth below):

```bash
python -m app.cli create-superuser --email you@example.com --password yourpassword --display-name "You"
```

Run the test suite with `pytest` (uses an in-memory SQLite DB, no Postgres needed for tests).

## Docker deployment

```bash
cp .env.example .env   # fill in SECRET_KEY, VAPID_*, CRON_SECRET
docker compose up -d --build
docker compose exec app python -m app.cli create-superuser --email you@example.com --password yourpassword --display-name "You"
```

This builds the frontend in a throwaway Node stage and ships only the compiled static output
in the final Python image — Node never runs at container runtime. Postgres runs as its own
`db` service. The reminder scheduler (`ENABLE_INTERNAL_SCHEDULER`) is on by default here, since
the container is a genuinely long-running process.

## Passenger (shared hosting) deployment

There's no Docker on shared hosting, so:

1. Build the frontend somewhere that has Node (locally, or in CI) and upload the result:
   ```bash
   cd frontend && npm install && npm run generate
   ```
   Upload the whole repo, including `frontend/.output/public/`, to the host. (Or, once you've
   cut at least one release — see below — skip this step entirely and let
   `scripts/passenger_update.py` install the first release for you instead of a manual upload.)
2. Install Python dependencies on the host (however your host expects — a virtualenv `pip
   install -e .` is typical) and run `alembic upgrade head` against your Postgres database.
3. Point Passenger's app root at the repo root; it picks up `passenger_wsgi.py` automatically.
4. Set environment variables (`SECRET_KEY`, `DATABASE_URL`, `VAPID_*`, `CRON_SECRET`, etc.) via
   whatever your host's control panel provides (cPanel's "Setup Python App" env var UI, or a
   `.env` file next to `passenger_wsgi.py` — the app reads `.env` automatically either way).
5. Leave `ENABLE_INTERNAL_SCHEDULER` unset/false — Passenger may recycle or idle its worker
   process, so an in-process scheduler can't be trusted to survive. Instead, set up a cron job
   in your host's control panel (e.g. every 15–30 minutes) hitting the tick endpoint:
   ```bash
   curl -fsS -X POST -H "X-Cron-Secret: $CRON_SECRET" https://your-domain/internal/cron/tick
   ```
6. **If the deploy fails** with Passenger complaining about the app object, your host's
   Passenger is likely old enough to be WSGI-only (native ASGI support needs Passenger ≥6).
   Set `PASSENGER_FORCE_WSGI=1` in the environment to wrap the app for that case instead of
   digging further — check the Passenger error log first to confirm that's actually the issue.

## Releases and updating Passenger

`.github/workflows/ci.yml` runs the backend test suite and a frontend build check on every
push/PR. Releases are handled by [release-please](https://github.com/googleapis/release-please)
(`.github/workflows/release-please.yml`, configured by `release-please-config.json` /
`.release-please-manifest.json`): it watches `master` and keeps a "release PR" up to date —
bumping `pyproject.toml`'s version and drafting `CHANGELOG.md` — from
[Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `feat!:`/
`BREAKING CHANGE:` for a major bump, etc.) merged since the last release. **Merging that PR is
the release** — release-please creates the version tag and GitHub Release itself, which
triggers a second job in the same workflow to build the frontend, re-run the tests, and attach
a `breidablik-release.tar.gz` asset (containing `app/`, `pyproject.toml`, `passenger_wsgi.py`,
`alembic.ini`, the prebuilt `frontend/.output/` — everything Passenger needs) to that release.

Only two things are needed for the PR-opening step to work: `pull-requests: write` /
`contents: write` are already granted in the workflow file, but the repo also needs **Settings
→ Actions → General → Workflow permissions → "Allow GitHub Actions to create and approve pull
requests"** turned on (a one-time setting, off by default); and every commit that should show
up in a release needs a Conventional Commits prefix — anything else is silently excluded from
both the changelog and the version-bump decision.

Since a shared host can't watch GitHub on its own, `scripts/passenger_update.py` is a
dependency-free script that does it from the other end — point a cron job at it (hourly or
daily; GitHub's unauthenticated API rate limit is 60/hour per IP, so don't go much tighter than
that without setting `GITHUB_TOKEN`):

```bash
0 4 * * * /path/to/venv/bin/python3 /path/to/scripts/passenger_update.py \
  --base-url https://your-domain --cron-secret "$CRON_SECRET" >> /path/to/update.log 2>&1
```

It checks the latest release against the version already on disk and, only if there's a newer
one: downloads it, backs up the current `app/`, `pyproject.toml`, `passenger_wsgi.py`,
`alembic.ini`, and `frontend/.output/` (restored automatically if anything below fails),
overlays the new versions of exactly those paths (everything else — `.env`, the `var/` avatar
uploads directory, a venv, `.git` — is left alone), reinstalls Python dependencies, runs
`alembic upgrade head`, and finally touches `tmp/restart.txt` so Passenger reloads the app —
only once every prior step has actually succeeded. It then calls
`POST /internal/cron/notify-update` on the running app so admins get notified in-app (and via
push, if configured) that the update landed. Run it with `--check-only` to just see whether an
update is available, or `--dry-run` to log what it would do without touching anything; `--help`
lists every flag (repo, paths, tokens — all also settable via environment variable).

## Environment variables

See `.env.example` for the full list with inline explanations. The ones you must set for a
real deployment: `SECRET_KEY` (long random string), `DATABASE_URL`, `VAPID_PUBLIC_KEY` /
`VAPID_PRIVATE_KEY` (generate with `py_vapid`, already a dependency — see `.env.example` for
the one-liner), `VAPID_CLAIM_EMAIL`, and `CRON_SECRET`. Set `COOKIE_SECURE=false` only for
local plain-http development — browsers refuse to set a `Secure` cookie over http.

`AVATAR_STORAGE_DIR` (default `var/avatars`) is where uploaded profile pictures live on local
disk, deliberately outside the deployed code tree so a Passenger update never touches them —
point it somewhere persistent if your host's app root can be wiped/recreated.

## Auth model

Registration is admin-created only (no public sign-up) — add members from Profile → Manage
members once logged in as a superuser, or bootstrap the very first account with
`python -m app.cli create-superuser`. Each member can optionally enable TOTP 2FA and set up a
PIN for quick-unlock on a specific trusted device, both from their Profile page.

## Notifications

Web Push requires the VAPID keys above; without them, push sending silently no-ops and
everything still works via the in-app notification log on Profile (this is also the reliable
fallback for browsers/situations where push isn't available, e.g. iOS Safari before the PWA is
added to the home screen). Each member can subscribe from Profile → Notifications.

## Profile pictures

Each member can upload a photo from Profile → Photo (JPEG/PNG/WebP, auto-cropped to a square
and resized). It shows up as a small avatar next to their name wherever a duty's current
assignee or an event's RSVP list is displayed; anyone without a photo gets a colored
initials circle instead. Stored as plain files under `AVATAR_STORAGE_DIR` — see Environment
variables above.

## Calendar subscription

Every member has a personal iCalendar feed URL (Profile → Subscribe to your calendar) that can
be added to Google/Apple/Outlook calendar as a URL subscription — it includes their own duty
occurrences and tasks, every collective event, and everyone's away dates.
