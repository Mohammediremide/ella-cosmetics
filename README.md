# Ella Cosmetics

Django REST API + React/Vite storefront and admin dashboard. Manual bank-transfer checkout, WhatsApp receipts, admin payment verification, dynamic store sections, inventory with audit trail, and a privacy-friendly visit counter. **No payment gateway.**

```
backend/    Django 5 + DRF (accounts, catalog, orders, core)
frontend/   React 18 + TypeScript + Vite + Tailwind (storefront at /, admin at /admin)
render.yaml Render blueprint (API + PostgreSQL + scheduled jobs)   frontend/vercel.json  Vercel config
```

## 1. Run it locally

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # set DJANGO_SECRET_KEY; keep DJANGO_DEBUG=true locally
python manage.py migrate                                 # also creates the 3 default sections
python manage.py createsuperuser                         # your admin login (no default credentials exist)
python manage.py seed_dev                                # OPTIONAL: clearly-labelled EXAMPLE products (dev only)
python manage.py runserver                               # http://localhost:8000   API docs: /api/docs/
```
Uses SQLite unless `DATABASE_URL` is set. To use PostgreSQL locally: `DATABASE_URL=postgres://user:pass@localhost:5432/ella`.

**Frontend**
```bash
cd frontend && npm install && npm run dev                # http://localhost:5173 (proxies /api and /media to :8000)
```
Open the site at **http://localhost:5173** (not 127.0.0.1: CSRF trusts `FRONTEND_ORIGIN`).

**First-run business setup** (Admin → Settings): bank name / account name / account number, WhatsApp number (defaults to `2348088317529`; any format like `+234 808 831 7529` is normalised), delivery & pickup options, unpaid-order window, legal-page details. Nothing business-specific is in source code.

## 2. How the store works

**Sections (categories).** Default sections: Accessories, Fragrance, Makeup. Admin → *Manage Sections*: create, rename, describe, add a cover image, activate/deactivate, reorder, see product counts. Names are unique ignoring case/whitespace. A section with products (even archived) can only be deactivated, never deleted. Deactivated sections and their products disappear from the shop and **cannot be bought** (listings, product page, cart and checkout all enforce this). A new product must be assigned to an active section.

**Checkout and payment.** Stock is reserved when the order is created. The order page shows the total, bank details (copy button), a WhatsApp link pre-filled with order number and amount, and the 5 steps. The customer presses **Done — I've Sent the Receipt** → status becomes *Processing — Awaiting Verification* (it never becomes paid by itself). In **Admin → Payment Verification** staff verify (after seeing the money in the bank) or reject (reason required). Payment status and fulfilment status are separate fields; every change is audited with who/when.

Payment statuses: Awaiting Payment → Processing — Awaiting Verification → Payment Successful / Payment Rejected (customer can resubmit). Cancelled orders read "Cancelled".

**Inventory policy.** Deducted at order creation; cancel or expiry restores exactly once; verify/reject/Done never touch stock. Every change is in the product's stock history. Unpaid (*Awaiting Payment* or *Rejected*) orders expire after the window in Admin → Settings (default 24 h). Orders where the customer pressed Done are **not** auto-expired: an admin must verify or reject them.

**Visits.** Admin → Overview shows visitors (unique per day) and page views for today / 7 / 30 days / all time, a daily chart and top pages. No cookies and no IP addresses are stored (daily-salted hash only); staff, bots and admin pages are excluded.

**Dark mode.** A sun/moon button in the header (and the mobile menu and admin sidebar) switches between light and dark. First-time visitors get whatever their phone/computer is set to; their choice is remembered on that device. Colours live in `frontend/src/index.css` (`:root` and `:root[data-theme='dark']`).

**Homepage slideshow.** Admin → *Homepage Slideshow*: upload MP4/WebM videos (up to 30 MB, ~10–20 s clips work best) or photos, add an optional headline, sub-text and button, reorder, hide or delete. Videos play muted, one after another; images show for 6 s. Visitors get pause/play, next/previous and dots (and reduced-motion users start paused). With no slides the homepage shows the default Ella Cosmetics banner. Products never appear in the hero. Videos on a live site are stored on Cloudinary (same `CLOUDINARY_URL`); keep clips short because they download to every visitor's phone.

**Product images.** No stock photography is bundled. Products and sections without a photo show a branded placeholder. **Upload real photos in Admin → Products (edit a product → Images)** and section covers in **Admin → Manage Sections**. "Featured" on the product form only controls the Featured row on the homepage.

## 3. Environment variables

Backend (`backend/.env.example` lists them all with comments):

| Variable | Required in production | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | yes | Signing key. App refuses to start without it. |
| `DJANGO_DEBUG` | yes → `false` | Must be `false` in production. |
| `DJANGO_ALLOWED_HOSTS` | yes | Comma-separated API hostnames. |
| `DATABASE_URL` | yes (app refuses to start without it) | Neon direct connection string. |
| `FRONTEND_ORIGIN` (+ `EXTRA_FRONTEND_ORIGINS`) | yes | CORS + CSRF trusted origin(s), e.g. `https://yourstore.com`. |
| `COOKIE_SAMESITE` | no (`Lax`) | `None` only if the browser calls the API host directly. |
| `CLOUDINARY_URL` | yes (app refuses to start without it) | `cloudinary://API_KEY:API_SECRET@CLOUD_NAME`. Backend only; never in frontend code. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | for password reset | SMTP. Without `EMAIL_HOST`, production silently discards reset emails. |
| `SECURE_SSL_REDIRECT`, `LOG_LEVEL` | no | Defaults `true`, `INFO`. |

Frontend: `VITE_API_BASE_URL` (leave empty; see below).

## 4. Tests

```bash
cd backend && python manage.py test                                              # SQLite
DATABASE_URL=postgres://user:pass@localhost:5432/ella python manage.py test      # PostgreSQL, also runs the concurrency tests
cd frontend && npm run lint && npm test && npm run build
```
The PostgreSQL run needs a role with CREATEDB (Django creates a throw-away `test_*` database).

## 5. Deployment (Vercel + Render + Neon + Cloudinary). Nothing here has been deployed by the author of this archive

Order matters: **Neon → Cloudinary → Render → Vercel → back to Render** (to tell it the final store URL).

| Service | Role | Where secrets go |
|---|---|---|
| Neon | PostgreSQL | connection string → Render env `DATABASE_URL` |
| Cloudinary | images + slideshow videos | `cloudinary://KEY:SECRET@CLOUD` → Render env `CLOUDINARY_URL` |
| Render (free web service) | Django API | all backend variables |
| Vercel | React storefront | no secrets (only the optional `VITE_API_BASE_URL`) |

**Why the browser must talk to ONE domain.** `*.vercel.app` and `*.onrender.com` are different sites, so a login cookie set by Render is a third-party cookie that Safari/iPhone and (increasingly) Chrome block. Two safe layouts:
1. **Vercel rewrite (default):** `frontend/vercel.json` proxies `/api` and `/media` to Render, so the browser only sees your store domain. Replace both `YOUR-BACKEND-HOST` values with your Render host (no `https://`).
2. **Custom domains (best for production):** `www.yourshop.com` (Vercel) and `api.yourshop.com` (Render) are the *same site*, so cookies work. Then set Vercel env `VITE_API_BASE_URL=https://api.yourshop.com`, and Render env `COOKIE_SAMESITE=Lax` (default).
Never set `COOKIE_SAMESITE=None` to "make it work": it still fails on Safari and weakens CSRF protection.

**Render free-plan facts.** The service sleeps after about 15 minutes without traffic (first request afterwards takes up to a minute), has no shell, no pre-deploy command and no cron jobs, and its disk is wiped on every deploy. So: migrations run inside the build command; images/videos live on Cloudinary; create the first admin locally (see below); the order-expiry job runs from GitHub Actions.

**Render settings:** Root directory `backend` · Build `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate --noinput` · Start `gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 60` · Health check path `/api/health/` · env `PYTHON_VERSION=3.12.3`. (`render.yaml` encodes all of this.)

**Neon:** use the **direct** (non-pooled) connection string. Django keeps its own connections and migrations need a direct session; the app already tests reused connections because Neon pauses idle databases. In production the app refuses to start if `DATABASE_URL`, `FRONTEND_ORIGIN` (https) or `CLOUDINARY_URL` are missing, so a forgotten variable can't silently lose data.

**First admin account (no Render shell on free plan):** on your own computer run `createsuperuser` against Neon by setting `DATABASE_URL` only in that terminal session (never in a file or in chat):
`export DATABASE_URL='...'` then `python manage.py migrate && python manage.py createsuperuser`, then `unset DATABASE_URL`.

**Scheduled order expiry:** `.github/workflows/expire-orders.yml` runs `expire_orders` hourly. Add GitHub repository secrets `DATABASE_URL` and `DJANGO_SECRET_KEY` (same values as Render) and run it once from the Actions tab to confirm. Until then, expiry is NOT running. Optional housekeeping: `python manage.py prune_pageviews --days 180`.

**Vercel plan.** Vercel's free Hobby plan is for non-commercial use only; a shop needs a paid plan (or another host that permits commercial use on its free tier, in which case use layout 2 above because rewrites differ by host). Check Vercel's current terms and pricing before launch.

**Password reset email:** configure `EMAIL_*` (any SMTP provider). Without it, production discards reset emails.

## 5b. Troubleshooting a deployed site
- **Banner "We're having trouble reaching the store server" (or products/sections missing):** the storefront cannot reach the API. Open `https://YOUR-STORE-URL/api/health/` — it must show `{"status": "ok"}`. If it shows your website or a blank page instead, check that `frontend/vercel.json` is inside the Vercel *Root Directory* (`frontend`) and that its API rewrite uses `/api/(.*)` as the source and `https://YOUR-RENDER-HOST/api/$1` as the destination, before the SPA fallback. Replace the host with the Render service that says *Deployed*. Push the fix and wait for Vercel to redeploy. If health shows an error from Render, open the Render service logs.
- **First visit after a quiet period is slow (up to ~1 minute):** Render's free plan sleeps when idle.

## 6. Known limitations / owner to-do
- Scheduler, Cloudinary, email delivery and the live deployment must be set up with your own accounts; they could not be verified here.
- Privacy and Terms pages are plain-language starters, not legal advice. Fill the highlighted gaps in Admin → Settings and have a Nigerian lawyer review them.
- Orders require a signed-in account. No emails are sent for orders (only password reset).
- API docs (`/api/docs/`) are thin for a few hand-written endpoints.
- Visitor counts treat a returning person as a new visitor each day by design.
