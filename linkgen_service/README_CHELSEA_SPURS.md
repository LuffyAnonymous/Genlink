# Chelsea + Spurs link finder

A separate, human-driven tool. It does **not** touch `LinkGeni.py` (Man
United) or anything in the main Flask app - Man United's automated flow is
unchanged.

Unlike Man United, Chelsea and Spurs aren't wired to an automated
login/API. This opens a real, visible browser window on your own machine,
lets *you* log in and handle any OTP/CAPTCHA yourself, then helps you find
the ticket link on the page - it never touches your password.

## Install (once)

From the project root, with the venv active:

```
pip install -r linkgen_service/requirements-addon.txt
playwright install chromium
```

## Run

```
python linkgen_service/multi_club_linkgen.py chelsea
python linkgen_service/multi_club_linkgen.py spurs
```

Optional match hint (helps you spot the right fixture on the page):

```
python linkgen_service/multi_club_linkgen.py chelsea --match "Liverpool"
```

A browser window opens. Log in normally, complete OTP/CAPTCHA if your
account needs it, then press ENTER in the terminal. The tool lists visible
ticket-looking links on the page and asks you to pick the right one.

## After you have the link

Go to the match's page in Genlinklab (Ticket Manager -> Chelsea/Spurs ->
the match), paste the Supporter ID/email and the link into the "Record a
ticket link" form there, and submit. That's what actually saves it and
spends the credit - it goes through the exact same storage/credit rules as
every other generated ticket, so it shows up on the Account page the same
way.

Your login session for the club site is kept in `browser_profile/` (created
automatically here) so you don't have to log in every single time. Nothing
in this folder is committed to git.
