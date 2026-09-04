# Stripe billing - how it works

Bank transfer has been fully replaced by Stripe Checkout. Credits (or the
unlimited pass) are added automatically the moment payment succeeds - no
admin confirmation step anymore.

## The flow

1. Customer picks an amount (or the unlimited pass) on `/credits/buy`.
2. `POST /credits/checkout` (`create_checkout_session()` in
   `app/billing/routes.py`) creates a `PaymentRequest` row (status
   `pending`) and a Stripe Checkout Session, then redirects the customer
   to Stripe's hosted payment page.
3. Customer pays on Stripe's page - card details never touch our server.
4. Stripe calls `POST /credits/webhook/stripe` (`stripe_webhook()`)
   server-to-server once payment actually succeeds. **This is the only
   place credits get added.** The signature is verified
   (`STRIPE_WEBHOOK_SECRET`) before anything happens - an unsigned/faked
   request gets rejected with 400 and nothing else runs.
5. Customer's browser is redirected to `GET /credits/return/<reference>`
   (`stripe_return()`), which only ever *displays* status - it never
   grants credits itself, since the redirect can be replayed or skipped.
   Normally the webhook has already landed by the time this loads
   (`transfer_confirmed.html`); on the rare race where it hasn't yet, it
   shows `stripe_processing.html` instead.

## What changed in the database

`BankTransferRequest` -> `PaymentRequest` (table `bank_transfer_requests`
-> `payment_requests`), with two new columns:
`stripe_checkout_session_id`, `stripe_payment_intent_id`.
`CreditTransaction.bank_reference` -> `payment_reference`.

Existing databases (including your local one) need the migration run
once:
```
flask --app wsgi.py migrate-stripe-billing
```
It's safe to re-run - every step checks first and skips what's already
done. No data is dropped; existing confirmed payments are kept exactly as
they were, just under the new table name.

## What's needed to actually go live

1. **Real Stripe keys** in `.env` (never commit these - `.env` is
   gitignored):
   ```
   STRIPE_SECRET_KEY=sk_test_...       # test mode first, always
   STRIPE_PUBLISHABLE_KEY=pk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```
   `flask --app wsgi.py check-config` will tell you if any of these are
   missing or still placeholders.

2. **A running webhook receiver** for local testing - the Stripe CLI:
   ```
   stripe login
   stripe listen --forward-to localhost:3001/credits/webhook/stripe
   ```
   This prints a `whsec_...` value - that's what goes in
   `STRIPE_WEBHOOK_SECRET` locally. Leave this running in a terminal
   while testing.

3. **A full run-through**: log in, go to `/credits/buy`, pick a package,
   pay with Stripe's test card `4242 4242 4242 4242` (any future
   expiry, any CVC), confirm you land back on a "credits added" page and
   the balance on `/account` actually increased.

4. **Once deploying for real**: register a webhook endpoint in the
   Stripe Dashboard -> Developers -> Webhooks, pointed at
   `https://<real-domain>/credits/webhook/stripe`, subscribed to
   **both** `checkout.session.completed` **and**
   `checkout.session.async_payment_succeeded` (see the payment_status note
   below for why both) - that gives you the production `whsec_...` to put
   in the real `.env`. Switch `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY`
   to the `sk_live_...` / `pk_live_...` keys only once everything above has
   been verified working in test mode.

## Security properties (already built in, worth knowing)

- Card numbers never touch this server - Stripe's hosted page handles them.
- The webhook's signature is verified on every request; anything that
  doesn't verify is rejected before touching the database.
- The webhook handler is idempotent - Stripe can and does redeliver
  events, and a duplicate delivery for an already-confirmed payment is a
  no-op (checked with the same row-lock pattern the old bank-transfer
  code used).
- `checkout.session.completed` fires as soon as checkout finishes, which
  for a delayed payment method (e.g. certain bank debits) is *before* the
  money has actually arrived - `payment_status` stays `"unpaid"` until
  Stripe later sends `checkout.session.async_payment_succeeded`. The
  webhook checks `payment_status == "paid"` before fulfilling anything, so
  a still-processing delayed payment can't grant credits early - it just
  waits for the async event, which fires once the payment genuinely
  clears.
- `/credits/return/<reference>` (what the customer's browser sees) never
  grants credits - only the webhook does. That route can be visited,
  refreshed, or guessed at without ever producing free credits.
