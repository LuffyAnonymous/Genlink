"""
Thin wrapper around your existing ticket-link generation API.

IMPORTANT: this is written generically because the exact contract of your
API (auth style, request/response shape) wasn't fully specified. Adjust
`call_link_generation_api` below to match it exactly - in particular:
  - how the API is authenticated (Bearer token shown below, swap for
    whatever you actually use)
  - the request payload shape sent to it
  - the response field names for the ticket link, match name, and event
    date (several common names are checked below - add yours if different)
  - what response indicates a genuine success vs a failure that should NOT
    consume a credit
"""
from datetime import datetime

import requests

try:
    from dateutil import parser as dateutil_parser
except ImportError:  # pragma: no cover - dateutil is in requirements.txt
    dateutil_parser = None


class LinkGenResult:
    def __init__(self, success: bool, link, raw: dict, match_name=None, event_date=None):
        self.success = success
        self.link = link
        self.raw = raw
        self.match_name = match_name
        self.event_date = event_date  # datetime or None


def _parse_event_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if dateutil_parser is not None:
        try:
            return dateutil_parser.parse(str(value))
        except (ValueError, TypeError, OverflowError):
            return None
    # Fallback without python-dateutil: try a couple of common formats
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def call_link_generation_api(payload: dict, app_config) -> LinkGenResult:
    url = app_config["LINKGEN_API_URL"]
    api_key = app_config["LINKGEN_API_KEY"]

    if not url:
        return LinkGenResult(False, None, {"error": "LINKGEN_API_URL is not configured"})

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
    except requests.Timeout:
        return LinkGenResult(
            False,
            None,
            {"error": "timeout", "message": "The link generator is taking longer than usual. Please try again in a minute."},
        )
    except requests.RequestException:
        return LinkGenResult(
            False,
            None,
            {"error": "request_failed", "message": "Couldn't reach the link generator. Please try again shortly."},
        )

    try:
        data = response.json()
    except ValueError:
        data = {"raw_text": response.text}
    if response.status_code==200:
        mydata=response.json().get('events','')
        if not mydata:
            return LinkGenResult(False, None, {"error": "No events found in response"})
        else:
            for x in mydata:
                indevent=mydata[x]
                if payload.get('match_name')==indevent.get('eventname') and payload.get('email')==indevent.get('supporterid'):
                    link=indevent.get('nfc')
                    match_name=indevent.get('eventname')
                    event_date_d=indevent.get('eventdate')
                    event_date = datetime.strptime(
                                event_date_d,
                                "%d/%m/%Y %H:%M"
                            )
                    return LinkGenResult(True, link, data, match_name=match_name, event_date=event_date)
                else:
                    return LinkGenResult(False, None, {"error": "No matching event found in response"})

    return LinkGenResult(False, None, {"status_code": response.status_code, "body": data})
