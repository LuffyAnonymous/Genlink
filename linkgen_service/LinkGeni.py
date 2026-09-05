import random
import base64
import hashlib
import re
import secrets
from curl_cffi import requests
from models import app, db, Ticket
import os
from concurrent.futures import ThreadPoolExecutor
from flask import request, jsonify

API_KEY = os.getenv("API_KEY")

executor = ThreadPoolExecutor(max_workers=10)
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs, unquote,urljoin

Host="login.manutd.com"

iphone_user_agents = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.7 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.7 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
]

android_user_agents = [
    "Mozilla/5.0 (Linux; Android 15; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; SM-S938B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-A556E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; OnePlus 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Xiaomi 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; 24030PN60G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A536B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A336B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-A525F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
]

browser_profiles = {
    "iphone_safari": [
        {
            "user-agent": ua,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "client_id": "app_apple",
            "device": "Apple"
        }
        for ua in iphone_user_agents
    ],

    "android_chrome": [
        {
            "user-agent": ua,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "client_id": "app_android",
            "device": "Android"
        }
        for ua in android_user_agents
    ],
}

def db_insert(validtickets):
    with app.app_context():

        # Get IDs that already exist
        existing_ids = {
            ticket.id_unique
            for ticket in Ticket.query.filter(
                Ticket.id_unique.in_(validtickets.keys())
            ).all()
        }

        # Build only new tickets
        tickets_to_insert = [
            {
                "id_unique": id_unique,
                "supporter_id": ticket["supporterid"],
                "event_name": ticket["eventname"],
                "event_date": ticket["eventdate"],
                "area_name": ticket["areaname"],
                "row_name": ticket["rowname"],
                "seat_name": ticket["seatname"],
                "nfc": ticket["nfc"],
                "owner_name": ticket["ownername"]
            }
            for id_unique, ticket in validtickets.items()
            if id_unique not in existing_ids
        ]

        if not tickets_to_insert:
            print("No new tickets to insert")
            return

        try:
            db.session.bulk_insert_mappings(
                Ticket,
                tickets_to_insert
            )

            db.session.commit()

            print(f"Inserted {len(tickets_to_insert)} new tickets")

        except Exception as e:
            db.session.rollback()
            print(f"Database error: {e}")

def Manunited(proxy,supporter_id,supporter_password):
    if not proxy:
        proxy = os.getenv("DEFAULT_PROXY")
    session=requests.Session()
    session.proxies={"https":f"http://{proxy}","http":f"http://{proxy}"}
    platform = random.choice(["iphone_safari", "android_chrome"])
    # platform = random.choice(["iphone_safari"])
    profile = random.choice(browser_profiles[platform])
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
    state = secrets.token_urlsafe(8)
    uba_id = secrets.token_hex(20)
    page_id = secrets.randbelow(10**16 - 10**15) + 10**15
    print(profile["user-agent"])
    headers = {
        "Host": Host,
        "upgrade-insecure-requests": "1",
        "user-agent": profile["user-agent"],
        "accept": profile["accept"],
        "accept-language": profile["accept-language"],
    }
    params = {
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'prompt': 'login',
        'redirect_uri': 'manutd://auth/callback',
        'client_id': profile["client_id"],
        'response_type': 'code',
        'state': state,
        'scope': 'openid profile full_profile ticketing offline_access status',
    }

    response = session.get('https://login.manutd.com/connect/authorize', params=params, headers=headers)
    # print(response)
    # open('response1.html', 'w', encoding='utf-8').write(response.text)
    req_token=re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', response.text)
    if not req_token:
        return {"error": "Request verification token not found"}
    else:
        req_token = req_token.group(1)
        
    # print(req_token)
    parsed = urlparse(response.url)
    if "ReturnUrl" not in parse_qs(parsed.query):
        return {"error": "ReturnUrl not found in the response URL"}
    else:
        return_url = parse_qs(parsed.query)["ReturnUrl"][0]
    
    headers = {
        'Host': 'login.manutd.com',
        'cache-control': 'max-age=0',
        'origin': 'https://login.manutd.com',
        'upgrade-insecure-requests': '1',
        'content-type': 'application/x-www-form-urlencoded',
        'user-agent': profile["user-agent"],
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'referer': response.url,
        'accept-language': profile["accept-language"],
    }

    params = {
        'ReturnUrl': return_url,
    }

    data = {
        'ReturnUrl': return_url,
        'RegToken': '',
        'Username': supporter_id,
        'Password': supporter_password,
        'DeviceTransactionID': '',
        'UbaID': uba_id,
        'PageID': page_id,
        'UbaSessionID': '',
        '__RequestVerificationToken': req_token,
    }

    response = session.post('https://login.manutd.com/sign-in', params=params, headers=headers, data=data,allow_redirects=False)
    # print(response)
    next_url=''
    while response.is_redirect:
        location = response.headers["Location"]
        next_url = urljoin(response.url, location)

        # print("Redirect:", next_url)

        # Stop when the redirect is to the mobile app
        if next_url.startswith("manutd://"):
            # print("App callback:", next_url)
            break
        
        response = session.get(next_url,headers=headers,allow_redirects=False)
    if "manutd://" not in next_url:
        return {"error": "Redirect to mobile app not found"}
    # print(response)
    if not re.search(r"code=(.*?)&", next_url):
        return {"error": "Code not found in the redirect URL"}
    mycode=re.search(r"code=(.*?)&", next_url).group(1)
    # print("Code:", mycode)
    trace_id = secrets.token_hex(16)    
    date_random_days_ago = (datetime.now(timezone.utc) - timedelta(days=secrets.randbelow(7) + 1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    cookies = {
        'userConsentCookiePolicy': 'on',
        'UserConsent': 'on',
        'CookiesSavedDateConsent': date_random_days_ago,
        'infoAgree': 'yes',
    }
    
    
    headers = {
        'Host': 'login.manutd.com',
        'accept': 'application/json, text/javascript; q=0.01',
        'baggage': f'sentry-environment=production,sentry-public_key=dbaae2fd62560b5ff2754ff862258595,sentry-trace_id={trace_id},sentry-org_id=450172',
        'content-type': 'application/x-www-form-urlencoded',
        'user-agent': profile["user-agent"],
        # 'user-agent': 'okhttp/4.12.0',
    }
    
    data = {
        'grant_type': 'authorization_code',
        'client_id': profile["client_id"],
        'scope': 'openid profile full_profile ticketing offline_access status',
        'code_verifier': code_verifier,
        'redirect_uri': 'manutd://auth/callback',
        'code': mycode,
    }

    response = session.post('https://login.manutd.com/connect/token', cookies=cookies, headers=headers, data=data)
    # print(response)
    # open('response2.html', 'wb').write(response.content)
    if 'id_token' not in response.json():
        return {"error": "ID token not found in the response"}
    idtoken = response.json().get('id_token')
    if not idtoken:
        return {"error": "ID token is empty"}
    headers = {
        'Host': 'sro-webapi.eu.seatgeekenterprise.com',
        'user-agent': f'EMEANativeSDK-{profile["device"]}-1.4.4',
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    # print(headers)
    params = {
        'tenantId': 'msdk.10026',
        'apiKey': 'testApiKey',
        'apiSecret': 'Cvrgd6DgpxCbBUqz3gPJ9LMU',
        'idToken': idtoken,
    }

    response = session.post('https://sro-webapi.eu.seatgeekenterprise.com/v1.0/sso/auth', params=params, headers=headers)
    # print(response)
    
    if 'access_token' not in response.text:
        return {"error": "Access token not found in the response"}
    elif 'clientId' not in response.text:
        return {"error": "Client ID not found in the response"}
    else:
        access_token = response.json().get('data').get('access_token')
        client_id = response.json().get('data').get('clientId')

    headers = {
        'Host': 'sro-webapi.eu.seatgeekenterprise.com',
        'authorization': f'Bearer {access_token}',
        
        'user-agent': f'EMEANativeSDK-{profile["device"]}-1.4.4',
    }

    params = {
        'getpastevents': '0',
        'includeTickets': 'true',
        'maxpagesize': '30',
        'includeNfc': 'true',
    }

    response = session.get(
        f'https://sro-webapi.eu.seatgeekenterprise.com/msdk.10026.prod/v1.0/profiles/{client_id}/events',
        params=params,
        headers=headers,
    )
    # print(response)
    # open('response4.html', 'wb').write(response.content)
    # print("ID Token:", idtoken)
    if 'data' not in response.json():
        return {"error": "Data not found in the response"}
    elif 'events' not in response.json().get('data'):
        return {"error": "No Events"}

    else:
        events = response.json().get('data').get('events')
        if not events:
            return {"error": "No tickets found"}
        else:
            validtickets={}
            for event in events:
                name=event.get('name')
                eventDate= event.get('formattedDate')
                for ticket in event.get('tickets', []):
                    id= ticket.get('id')
                    ticketinfo=ticket.get('printedTicketInfo')
                    linkinfo=ticket.get('ticketInfo')
                    id_unique= linkinfo.get('id')
                    areaname=ticketinfo.get('areaName')
                    rowname=ticketinfo.get('rowName')
                    seatname=ticketinfo.get('seatName')
                    nfc=linkinfo.get('nfc').removesuffix("?servicepartner=GOOGLE_PAY")
                    supid=ticketinfo.get('ownerCrmId')
                    ownername=ticketinfo.get('ownerName')
                    validtickets[id_unique]={"supporterid":supid,"eventname":name,"eventdate":eventDate,"areaname":areaname,"rowname":rowname,"seatname":seatname,"nfc":nfc,"ownername":ownername}
            if validtickets:
                db_insert(validtickets)
            return {"events": validtickets}
        


# supporter_id = '8336898'
# supporter_password = 'Michael%34jones'
# proxy='ViMfzi4i0uzAX34H:ckNoMTTVmLDTjLJG@geo.floppydata.com:10080'
# print(Manunited(Host,proxy,supporter_id,supporter_password))



@app.route("/api/manutd", methods=["POST"])
def manutd_api():

    # Check API key
    provided_key = request.headers.get("X-API-Key")

    if not provided_key or provided_key != API_KEY:
        return jsonify({
            "error": "Invalid or missing API key"
        }), 401

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "JSON body is required"
        }), 400

    supporter_id = data.get("email")
    supporter_password = data.get("password")
    proxy = data.get("proxy", None)

    if not supporter_id or not supporter_password:
        return jsonify({
            "error": "supporter_id and supporter_password are required"
        }), 400

    # Submit to the pool.
    # If 10 are already running, this waits in the executor queue.
    future = executor.submit(
        Manunited,
        proxy=proxy,
        supporter_id=supporter_id,
        supporter_password=supporter_password
    )

    try:
        result = future.result()

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 4000)),
        debug=False,
        threaded=True
    )