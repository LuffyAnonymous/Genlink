"""Premier League club list for the Ticket Manager screen.

Club names are factual data, not creative/branded assets - deliberately NOT
using official crests here (those are trademarked and weren't provided as
licensed assets), just a colour + initials badge per club so the UI still
reads at a glance. Swap in licensed crest images later if you have the
rights to use them.
"""
CLUBS = [
    {"slug": "liverpool", "name": "Liverpool", "color": "#C8102E", "logo": "liverpool.png"},
    {"slug": "arsenal", "name": "Arsenal", "color": "#EF0107", "logo": "arsenal.png"},
    {"slug": "chelsea", "name": "Chelsea", "color": "#034694", "logo": "chelsea.png"},
    {"slug": "man-utd", "name": "Man Utd", "color": "#DA291C", "logo": "manutd.png"},
    {"slug": "man-city", "name": "Man City", "color": "#6CABDD", "logo": "mancity.png"},
    {"slug": "spurs", "name": "Spurs", "color": "#132257", "logo": "spurs.png"},
    {"slug": "aston-villa", "name": "Aston Villa", "color": "#670E36", "logo": "astonvilla.png"},
    {"slug": "fulham", "name": "Fulham", "color": "#000000", "logo": "fulham.png"},
    {"slug": "newcastle", "name": "Newcastle", "color": "#241F20", "logo": "newcastle.png"},
    {"slug": "brentford", "name": "Brentford", "color": "#E30613", "logo": "brentford.png"},
]

def get_club(slug):
    return next((c for c in CLUBS if c["slug"] == slug), None)
