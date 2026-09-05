from __future__ import annotations

from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


CLUBS = {
    "chelsea": {
        "name": "Chelsea",
        "url": "https://www.chelseafc.com/",
        "ticket_labels": ["Manage Tickets", "Tickets", "My Tickets"],
    },
    "spurs": {
        "name": "Spurs",
        "url": "https://www.tottenhamhotspur.com/account",
        "ticket_labels": ["eTicketing", "Ticketing Hub", "Tickets", "My Tickets"],
    },
}

PROFILE_DIR = Path(__file__).resolve().parents[1] / "browser_profile"


def _click_first_visible(page, labels):
    for label in labels:
        try:
            loc = page.get_by_text(label, exact=True).first
            if loc.is_visible(timeout=1500):
                loc.click()
                page.wait_for_timeout(1500)
                return True
        except Exception:
            pass

        try:
            loc = page.get_by_role("link", name=label, exact=True).first
            if loc.is_visible(timeout=1500):
                loc.click()
                page.wait_for_timeout(1500)
                return True
        except Exception:
            pass

    return False


def _ticket_links(page):
    keywords = (
        "ticket", "eticket", "myticket", "manage-ticket",
        "manage_ticket", "seat", "match", "fixture"
    )
    found = []
    seen = set()

    for a in page.locator("a").all():
        try:
            href = a.get_attribute("href")
            text = (a.inner_text() or "").strip()
            if not href:
                continue
            full = href if href.startswith("http") else page.url.rstrip("/") + "/" + href.lstrip("/")
            hay = f"{text} {href}".lower()
            if any(k in hay for k in keywords):
                if full not in seen:
                    seen.add(full)
                    found.append((text, full))
        except Exception:
            continue

    return found


def generate(club: str, match_hint: Optional[str] = None) -> Optional[str]:
    club = club.lower().strip()
    if club not in CLUBS:
        raise ValueError("This add-on supports only Chelsea and Spurs.")

    cfg = CLUBS[club]
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1440, "height": 900},
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(cfg["url"], wait_until="domcontentloaded", timeout=60000)

        print(f"\nOpened {cfg['name']}.")
        print("Log in normally in the browser if required.")
        input("After you are logged in and the ticket page is ready, press ENTER here... ")

        _click_first_visible(page, cfg["ticket_labels"])

        if match_hint:
            try:
                match = page.get_by_text(match_hint, exact=False).first
                if match.is_visible(timeout=3000):
                    match.click()
                    page.wait_for_timeout(1500)
            except Exception:
                pass

        links = _ticket_links(page)

        if not links:
            print("\nNo visible ticket links were found on the current page.")
            print("You can navigate to the match/ticket page manually, then press ENTER.")
            input()
            links = _ticket_links(page)

        if not links:
            context.close()
            return None

        print("\nVisible ticket-related links:")
        for i, (text, href) in enumerate(links, 1):
            print(f"{i}. {text or '(no text)'}")
            print(f"   {href}")

        while True:
            choice = input(f"\nChoose a link (1-{len(links)}), or ENTER to cancel: ").strip()
            if not choice:
                context.close()
                return None
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(links):
                    selected = links[idx][1]
                    Path("generated_links.txt").open("a", encoding="utf-8").write(
                        f"{cfg['name']}\t{selected}\n"
                    )
                    print(f"\nSelected link:\n{selected}")
                    context.close()
                    return selected
            except ValueError:
                pass
            print("Invalid choice.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("club", choices=["chelsea", "spurs"])
    parser.add_argument("--match", default=None)
    args = parser.parse_args()

    generate(args.club, args.match)
