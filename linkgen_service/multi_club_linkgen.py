from providers.browser_club import generate

SUPPORTED_CLUBS = {"chelsea", "spurs"}


def generate_link(club: str, match_hint: str = ""):
    """
    Chelsea/Spurs-only add-on.

    Manchester United is intentionally not handled here so the existing
    Manchester United implementation remains untouched.
    """
    club = club.lower().strip()
    if club not in SUPPORTED_CLUBS:
        raise ValueError(
            "This add-on handles only Chelsea and Spurs. "
            "Leave the existing Manchester United generator unchanged."
        )
    return generate(club, match_hint or None)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Chelsea + Spurs link generator")
    parser.add_argument("club", choices=sorted(SUPPORTED_CLUBS))
    parser.add_argument("--match", default="")
    args = parser.parse_args()

    generate_link(args.club, args.match)
