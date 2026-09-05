# Contributing to Genlinklab

This is for anyone joining the project to build club automation, or to work
on the app itself. If you just want to run the app locally, see
[README.md](README.md) first - this doc assumes that's already working.

## What this app actually does

Genlinklab is a customer portal for a ticket-link-generation service. In
plain terms:

1. A customer registers, and an admin manually approves the account (email
   with a one-click approve link).
2. The customer buys **credits** by bank transfer - GBP 1 = 1 credit - or a
   flat **£999 unlimited-for-30-days pass**. Either way, an admin manually
   confirms the transfer arrived (another one-click email link) before
   anything is added to the account. There's no payment gateway; it's
   entirely manual, on purpose - no way to fake a payment.
3. The customer picks a club and match, then submits their own ticketing
   account (Supporter ID/email + password) for that club's site.
4. The app calls that club's **automation service** - a small program that
   actually logs into the club's real ticketing platform and pulls back the
   customer's digital ticket link (NFC pass, addable to Apple/Google
   Wallet).
5. A credit is only ever spent when step 4 **succeeds**. A failed attempt
   costs nothing. The same account+match combo is never charged twice -
   the app dedupes and just returns the existing link.

Right now:
- **Manchester United** is the only club with real, working automation
  (`linkgen_service/LinkGeni.py` - logs in via OAuth, exchanges tokens with
  the ticketing backend, returns the NFC link).
- **Chelsea and Spurs** currently only have a manual fallback: someone
  finds the link by hand and pastes it into the app. **This is the current
  priority** - upgrade both to real automation, matching Man Utd exactly
  (same contract below, same pattern as `LinkGeni.py`). Do this before
  starting any new club.
- **Liverpool, Arsenal, Man City, Aston Villa, Fulham, Newcastle,
  Brentford** aren't wired up at all yet - manual or automated, nothing
  exists for these. Lower priority than Chelsea/Spurs for now.

## Architecture in one picture

```
                    ┌─────────────────────────────┐
  customer  ─POST──▶│   Genlinklab (this repo)     │
  browser           │   Flask app - public on      │
                     │   GitHub, no real secrets    │
                     └──────────────┬────────────────┘
                                     │ POST {email, password, proxy}
                                     │ per club, own URL + API key
                     ┌───────────────┼───────────────┬───────────────┐
                     ▼               ▼               ▼               ▼
              Man Utd service  Chelsea svc.    Spurs svc.     (later: every
              (already built)  (build this     (build this     other club,
                                 next)           next)           private too)
```

The shared app (everything in `app/`) is public, on GitHub, and contains no
real credentials. Each club's actual automation - the part that logs into
that club's real ticketing site - is a **separate, private service** that
never gets committed to this repo. That split exists on purpose: club
automation typically embeds a proxy credential, a reverse-engineered login
flow, and an API key, none of which should be public or shared between
contributors who don't need each other's.

## The contract: how your club's service plugs in

Your automation just needs to be a small HTTP service (Flask, FastAPI,
whatever) that:

**Accepts** `POST` with a JSON body:
```json
{"email": "supporter-id-or-email", "password": "...", "proxy": "user:pass@host:port or null"}
```
and an `X-API-Key` header matching whatever key you choose.

**Returns**, on success, HTTP 200:
```json
{"events": {
  "<some-unique-ticket-id>": {
    "supporterid": "...",
    "eventname": "Manchester United v Everton",
    "eventdate": "06/09/2026 14:00",
    "nfc": "https://.../digital-pass/...",
    "areaname": "...", "rowname": "...", "seatname": "...", "ownername": "..."
  }
}}
```
`eventname` must match the app's match name exactly (`"{home_team} v
{away_team}"`), and `supporterid` must match the `email` field the customer
submitted - the app matches on both to find the right ticket in your
response. `eventdate` is parsed leniently (day-first), so close variants of
that format are fine.

**Returns**, on failure, anything else (a 4xx/5xx, or 200 with no matching
event) - the app treats that as "no credit charged, try again."

Look at `linkgen_service/LinkGeni.py` (not in git - ask a teammate who has
it, or work from `app/utils/linkgen.py` which documents the exact contract
it expects) for a complete working example against Man Utd's site.

### Wiring your service into the app

Once your service is running somewhere, no code changes are needed in this
repo. Just add two lines to `.env`:

```
LINKGEN_API_URL_CHELSEA=https://your-chelsea-service/api/generate
LINKGEN_API_KEY_CHELSEA=whatever-key-you-chose
```

(Slug uppercased, hyphens to underscores - `aston-villa` becomes
`ASTON_VILLA`. See `app/clubs.py` for the exact slugs.) The app looks this
up automatically per request based on which club the customer picked -
`app/config.py`'s `LINKGEN_CLUBS` and `app/utils/linkgen.py`'s
`call_link_generation_api()`.

Once your `.env` entries exist, add your club to the active list in
`app/templates/main/ticket_manager.html` (the `club.slug in (...)` check)
so customers can actually select it.

## Rules that matter

- **Never commit anything under `linkgen_service/`, `.env`, or any real API
  key/proxy credential/database password.** All of that is already
  gitignored - keep it that way. If you're not sure whether something's
  sensitive, ask before committing it.
- **Never touch `run_link_job()` in `app/services/link_jobs.py` for
  another club's sake.** It's deliberately generic and already handles
  every club through the same contract above. If your club needs something
  genuinely different (like the Chelsea/Spurs manual fallback did), that's
  a design conversation first, not a silent branch inside the shared
  function.
- **A credit must only ever be spent on genuine success.** Don't relax that
  check, even temporarily, even on a branch.
- Match the existing code style - no comments explaining *what* the code
  does, only *why* something non-obvious is the way it is.

## Current priority: automate Chelsea + Spurs

Don't start on Liverpool or any other new club yet. Chelsea and Spurs come
first - both need to be fully automated, matching Man Utd exactly, with no
manual fallback left for either.

```
                    ┌───────────────────────────────────┐
                    │  Goal: Chelsea + Spurs automated,    │
                    │  same as Man Utd's LinkGeni.py        │
                    └──────────────────┬────────────────────┘
                                       │
                    ┌──────────────────▼────────────────────┐
                    │  Does multi_club_linkgen.py (or the      │
                    │  Chelsea/Spurs zip already floating       │
                    │  around) already complete a real login    │
                    │  and return ticket data?                   │
                    └───────┬───────────────────────┬─────────┘
                       YES  │                        │  NO / NOT SURE
              ┌─────────────┘                        └─────────────┐
              ▼                                                     ▼
   ┌─────────────────────┐                              ┌─────────────────────┐
   │      PATH A            │                              │      PATH B            │
   │   Reuse & wrap it        │                              │   Build from scratch    │
   │   (fast - hours)         │                              │   (slower - needs real  │
   │                           │                              │    accounts, iteration) │
   └───────────┬─────────────┘                              └───────────┬─────────────┘
               │                                                        │
               └───────────────────────┬────────────────────────────────┘
                                       ▼
                    ┌───────────────────────────────────┐
                    │  Both converge here: an HTTP service │
                    │  matching the contract above -         │
                    │  test for real, wire into .env, then     │
                    │  activate in the UI                       │
                    └───────────────────────────────────┘
```

### Path A - reuse existing work

`linkgen_service/multi_club_linkgen.py` and `Tixlinx_Chelsea_Spurs_New_File.zip`
have already been referenced in a prior commit - track down whoever built
them first. Find out whether that tool already completes a real login and
pulls real ticket data, or whether it's just a helper for a *person* to
look at and copy a link by hand.

1. Get the file/zip from whoever has it. It stays private, the same way
   the rest of `linkgen_service/` does - never put it in git.
2. Check what it actually does: does it complete a real login and return
   genuine ticket/NFC data, or does it only assist a human?
3. If it returns real ticket data (even in a different shape than
   `LinkGeni.py`'s), wrap it in the same small Flask service pattern -
   `POST` in, `{"events": {...}}` out, `X-API-Key` auth.
4. Test it for real: `flask --app wsgi.py test-linkgen --email ...
   --password ... --match-name "Chelsea v ..."` - needs one real Chelsea
   account and one real Spurs account. No shortcuts - a link that was
   never verified against the real site isn't done.
5. Wire it in: `LINKGEN_API_URL_CHELSEA` / `LINKGEN_API_KEY_CHELSEA` (and
   the same for Spurs) in `.env`. No shared app code changes needed.

### Path B - build from scratch

If the existing material doesn't have a working login flow yet:

1. Get one real Chelsea ticketing account and one real Spurs account -
   used only for live test calls, never stored, never committed anywhere.
2. Investigate each club's actual login flow the way `LinkGeni.py` was
   built for Man Utd - watch what a real login form actually sends over
   the network. Chelsea and Spurs might share Man Utd's ticketing backend
   (SeatGeek Enterprise) - plenty of Premier League clubs use the same
   vendor - but verify that, don't assume it.
3. Get a bare login working first (proves auth), then extend it to fetch
   real ticket/NFC data.
4. Wrap it in the same contract as Path A steps 3-5.

### Once a club is actually automated

1. Confirm it's in `ticket_manager.html`'s active-club list (already true
   for Chelsea/Spurs, since they're on the manual fallback today).
2. Remove the manual-link form for that club - once it's automated, the
   fallback in `match_generate.html` / `app/services/manual_link.py` is no
   longer needed for it.
3. Update the "Right now" status list near the top of this doc.

## Git workflow

1. **One branch per club** (or per task): `automation/chelsea`,
   `automation/spurs`, etc. Branch off `main`.
2. **Small, focused commits** - your club's service lives outside this
   repo anyway, so commits here should just be the `.env.example` entry
   (documenting the two new variables, no real values) and the
   `ticket_manager.html` activation line, once your service is actually
   tested and working.
3. **Open a PR against `main`** when ready. Describe what you tested it
   against (a real account, a real match) - not just "it runs."
4. **Wait for review** before merging - don't merge your own PR.
5. Keep your branch up to date with `main` (`git pull --rebase origin
   main`) rather than letting it drift for a long time.

```bash
git clone https://github.com/LuffyAnonymous/Genlink.git
cd Genlink
git checkout -b automation/chelsea
# ... build your service elsewhere, test it against the running app ...
git add .env.example app/templates/main/ticket_manager.html app/templates/main/match_generate.html
git commit -m "Automate Chelsea link generation, retire the manual fallback"
git push -u origin automation/chelsea
# then open a PR on GitHub
```

## Questions

If something about the contract doesn't fit your club's actual login flow
(2FA, a CAPTCHA, a different token exchange), that's expected - every
club's ticketing platform is different. Get your service returning the
right JSON shape above and the app doesn't need to know or care how you
got there.
