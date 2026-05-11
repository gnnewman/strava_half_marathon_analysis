import marimo

__generated_with = "0.23.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    from dotenv import load_dotenv
    import requests
    import json
    from datetime import datetime, timezone
    import time

    load_dotenv()

    CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
    REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

    if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
        raise ValueError("Missing credentials for Strava API.")
    return (
        CLIENT_ID,
        CLIENT_SECRET,
        REFRESH_TOKEN,
        datetime,
        json,
        os,
        requests,
        time,
        timezone,
    )


@app.cell
def _(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, requests):
    def get_access_token(client_id, client_secret, refresh_token):
        resp = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id":     client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type":    "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    ACCESS_TOKEN = get_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
    return (ACCESS_TOKEN,)


@app.cell
def _(datetime, timezone):
    CACHE_PATH   = "strava_data.json"
    DATE_FROM    = datetime(2026, 2, 16, tzinfo=timezone.utc)
    DATE_TO      = datetime(2026, 5, 9,  tzinfo=timezone.utc)
    CACHE_KEY    = f"{DATE_FROM.date()}_{DATE_TO.date()}"
    return CACHE_KEY, CACHE_PATH, DATE_FROM, DATE_TO


@app.cell
def _(
    ACCESS_TOKEN,
    CACHE_KEY,
    CACHE_PATH,
    DATE_FROM,
    DATE_TO,
    json,
    os,
    requests,
    time,
):
    def fetch_runs(access_token, date_from, date_to):
        after_ts  = int(date_from.timestamp())
        before_ts = int(date_to.timestamp())
        headers   = {"Authorization": f"Bearer {access_token}"}
        activities, page = [], 1

        while True:
            resp = requests.get(
                "https://www.strava.com/api/v3/athlete/activities",
                headers=headers,
                params={"after": after_ts, "before": before_ts, "per_page": 100, "page": page},
            )

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("X-RateLimit-Reset", 60))
                time.sleep(retry_after)
                continue

            resp.raise_for_status()
            time.sleep(1)

            batch = resp.json()
            if not batch:
                break

            activities.extend(batch)
            page += 1

        return [a for a in activities if a.get("sport_type") == "Run"]

    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            cache = json.load(f)

    if CACHE_KEY in cache:
        print(f"loaded {len(cache[CACHE_KEY])} runs from cache")
        raw_runs = cache[CACHE_KEY]
    else:
        print("fetching runs from Strava API...")
        raw_runs = fetch_runs(ACCESS_TOKEN, DATE_FROM, DATE_TO)
        cache[CACHE_KEY] = raw_runs
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
        print(f"{len(raw_runs)} runs fetched and cached")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
