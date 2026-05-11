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
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import numpy as np

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
        mo,
        os,
        pd,
        plt,
        requests,
        ticker,
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
    return (raw_runs,)


@app.cell
def _(pd, raw_runs):
    def build_df(runs):
        rows = []
        for a in runs:
            rows.append({
                "id": a["id"],
                "name": a["name"],
                "date": pd.to_datetime(a["start_date_local"]),
                "distance_km": round(a["distance"] / 1000, 2),
                "moving_time_min": round(a["moving_time"] / 60, 1),
                "elapsed_time_min": round(a["elapsed_time"] / 60, 1),
                "elevation_m": a.get("total_elevation_gain", 0),
                "avg_hr": a.get("average_heartrate"),
                "max_hr": a.get("max_heartrate"),
                "avg_speed_kmh": round(a["average_speed"] * 3.6, 2),
                "suffer_score": a.get("suffer_score"),
                "workout_type": a.get("workout_type"),
                "trainer": a.get("trainer", False),
                "achievement_count": a.get("achievement_count"),
                "kudos_count": a.get("kudos_count")
            })

        df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
        df["pace_min_per_km"] = df["moving_time_min"] / df["distance_km"]
        df["week"] = df["date"].dt.to_period("W")
        df["week_num"] = (df["week"] - df["week"].min()).apply(lambda x: x.n) + 1
        return df

    df = build_df(raw_runs)
    df.head()
    return (df,)


@app.cell
def _(df, mo):
    weekly = (
        df.groupby("week_num")
        .agg(
            runs=("id", "count"),
            total_km=("distance_km", "sum"),
            longest_km=("distance_km", "max"),
            avg_pace=("pace_min_per_km", "mean"),
            avg_hr=("avg_hr", "mean"),
            elevation_m=("elevation_m", "sum"),
        )
        .round(2)
        .reset_index()
    )

    mo.ui.table(weekly)
    return (weekly,)


@app.cell
def _(plt, ticker, weekly):
    fig1, ax1 = plt.subplots(figsize=(10, 4))

    ax1.bar(
        weekly["week_num"], weekly["total_km"],
        color="#4A90D9", alpha=0.85, width=0.6, label="Weekly km",
    )

    rolling    = weekly["total_km"].rolling(4, min_periods=1).mean()
    pct_change = weekly["total_km"].pct_change()

    ax1.plot(weekly["week_num"], rolling, color="#E8593C", linewidth=2, linestyle="--", label="4-week rolling avg")

    for i, (w, pct) in enumerate(zip(weekly["week_num"], pct_change)):
        if pct > 0.10:
            ax1.annotate(
                f"+{pct*100:.0f}%",
                xy=(w, weekly["total_km"].iloc[i]),
                xytext=(0, 6), textcoords="offset points",
                ha="center", fontsize=8, color="#E8593C",
            )

    ax1.set_xlabel("Week")
    ax1.set_ylabel("km")
    ax1.set_title("Weekly volume")
    ax1.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax1.legend()
    ax1.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.gca()
    return


if __name__ == "__main__":
    app.run()
