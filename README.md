# Genlinklab

A customer portal built with Flask:

- Customer registration that requires **manual approval by email** (`admin@genlinklab.co.uk`) before the account can log in
- **PostgreSQL** via SQLAlchemy
- **Stripe Checkout** to buy credits, GBP 1 = 1 credit, with credits added automatically via webhook the moment payment succeeds
- A `/api/generate-link` endpoint that only spends a credit when your link-generation API call **succeeds**
- A dashboard with a ticket-stub visual identity

Tested locally with SQLite + a mocked mail/link-gen layer - the full registration → admin-approval → login → buy-credits → generate-link flow all pass. You still need to plug in your real PostgreSQL, SMTP, and link-generation credentials before going live (see below).

## 1. Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure

```bash
cp .env.example .env
```

Then fill in `.env`:

| Variable | What it's for |
|---|---|
| `SECRET_KEY` | Flask session signing - generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Your PostgreSQL connection string |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` | SMTP credentials for the mailbox that sends the admin notification + welcome email. Defaults are set for Office 365 - change if you use Gmail, SES, etc. |
| `ADMIN_EMAIL` | Where new-registration emails go (defaults to `admin@genlinklab.co.uk`) |
| `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET` | From your Stripe Dashboard - see `STRIPE_INTEGRATION.md` |
| `LINKGEN_API_URL` / `LINKGEN_API_KEY` | Your existing link-generation API |

## 3. Set up PostgreSQL

Create the database, then create the tables:

```bash
flask --app wsgi.py init-db
```

## 4. Stripe payments

Customers pay by Stripe Checkout. The flow:

1. Customer picks a credit amount (or the unlimited pass) on `/credits/buy` and submits it.
2. A `PaymentRequest` row is created and the customer is redirected to a Stripe-hosted checkout page.
3. Stripe calls `/credits/webhook/stripe` once payment actually succeeds - that webhook is the **only** place credits get added (never the browser redirect back to our site, since that can be replayed/spoofed), and it's idempotent (a duplicate webhook delivery for the same event does nothing the second time).

See `STRIPE_INTEGRATION.md` for the full setup (API keys, webhook registration, local testing with the Stripe CLI).

## 5. Wire up your link generation API

Open `app/utils/linkgen.py`. It's written generically because your API's exact contract (auth method, request/response shape) wasn't specified - update:

- The `Authorization` header if you don't use a Bearer token
- The request payload shape
- The response field the generated link is read from (`link`, `url`, `checkout_url` are checked by default)
- What counts as "success" — right now any 2xx response with a link field in the body deducts a credit; anything else (non-2xx, network error, or a 2xx with no link) does not

The credit balance check + deduction is done with a row lock (`SELECT ... FOR UPDATE`) so two simultaneous requests from the same user can't both slip through and overspend.

## 6. Run it

```bash
flask --app wsgi.py run --debug
# or in production:
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

## How the pieces fit together

- **Registration** (`app/auth/routes.py`): customer submits the form → account is created with `is_approved=False` → a single-use, 7-day-expiring token is generated → an email goes to `ADMIN_EMAIL` with their details and an approve link (`/admin/confirm/<token>`) → customer sees a "pending" page and can't log in yet.
- **Approval**: admin clicks the link in the email (no login needed - the token itself is the credential) → account flips to approved → customer gets a welcome email → customer can now log in.
- **Credits**: `/credits/buy` → customer submits an amount → a `PaymentRequest` is created and the customer is redirected to Stripe Checkout → Stripe calls `/credits/webhook/stripe` on success, which is what actually adds the credits → customer lands back on `/credits/return/<reference>`, which only ever displays status, never grants credits itself.
- **Ticket Manager**: `/tickets` shows a club grid → `/tickets/<club>` lists upcoming matches for that club (seeded for now with Manchester United v Ipswich Town) → `/tickets/<club>/<match_id>` is where a customer runs accounts against that match, either one at a time or via CSV.
- **Link generation & persistence** (`app/services/link_jobs.py`): every account+match attempt goes through one shared function. It looks up whether that exact account has already generated a link for that exact match - if so, the existing link is returned and **no credit is charged**. Otherwise it calls your API, and only on success does it deduct 1 credit and save a `GeneratedTicket` row (link, match name, event date parsed from your API's response, and the generation timestamp). The dashboard reads from that table, splitting into "Upcoming" (event date in the future, or unknown) and "Previous" (event date has passed).
- **CSV bulk upload**: the downloadable template has the match name pre-filled; each row is run through the same shared function, so duplicate accounts within a CSV (or accounts already run individually before) are skipped for credit purposes too. The batch stops early if the balance runs out partway through.

## Security notes worth knowing about

- Passwords are hashed with Werkzeug's `generate_password_hash` (PBKDF2) for Genlinklab's own login system.
- **Ticketing account passwords** submitted via the single-account form or CSV upload (for your automation bot) are *never written to the database or to logs* - they're forwarded straight to your link generation API and redacted (`***redacted***`) before anything is persisted. If you later need to reuse a saved account's credentials rather than just its resulting ticket link, you'd need to add encryption-at-rest (e.g. Fernet with a key held outside the database) - that isn't included here since the current design avoids storing them at all.
- CSV uploads are capped at 200 rows and 2MB per request (`MAX_CONTENT_LENGTH` in `app/config.py`) to avoid very long-running requests - raise these if you need bigger batches, but consider moving bulk processing to a background job/queue (Celery, RQ) rather than a synchronous request once batches get large.
- CSRF protection (Flask-WTF) is on globally.
- The admin approval link is a random token (`secrets.token_urlsafe`) and isn't guessable, single-use, and expires after 7 days. The Stripe webhook is authenticated by signature verification (`STRIPE_WEBHOOK_SECRET`), not a token in a URL - see `STRIPE_INTEGRATION.md`.
- Consider adding rate limiting (e.g. `Flask-Limiter`) on `/register`, `/login`, and `/api/generate-link` before going to production - it isn't included here.
- Consider adding a captcha (e.g. hCaptcha) on `/register` if you get spam signups, since the admin gets an email per submission.
- Club badges use each club's primary colour + initial rather than official crests, since crest artwork is trademarked and wasn't provided as a licensed asset - swap in your own licensed images in `app/templates/main/ticket_manager.html` / `club_matches.html` / `match_generate.html` if you have the rights to use them.
