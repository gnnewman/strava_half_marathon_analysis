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
    from matplotlib.patches import Patch
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
        Patch,
        REFRESH_TOKEN,
        datetime,
        json,
        mo,
        np,
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


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Let's get some data!
    I want to fetch all the runs from my 12-week training program, which started on February 16, 2026 and ended on May 9, 2026 (race day!).

    I've written this to respect the rate limit of the Strava API: 100 calls every 15 minutes. Although I don't think I did >8 runs a week, it's best to bake this in anyway.

    Finally, the API should only get called once– the first time you run this script. The returned data will get cached in JSON format. This cell will check if data has already been ingested before making any requests, avoiding any unnecessary calls. As one of my undergrad writing professors always said: "Do it nice, or do it twice."
    """)
    return


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


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Now that I've gotten ahold of my data, I've picked out some features that may be relevant to my analysis. In my persistent fight against using the Imperial System, I've converted all distance measurements to km-based units.
    """)
    return


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


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Weekly Load
    With my features in order, the first thing I want to look at is how much I was *doing* each week. A few significant family emergencies happened in April, so I expect there to be some variation in my training load around those weeks.

    According to [Coros](https://coros.com/stories/coros-coaches/c/half-marathon-training-guide), an optimal half marathon training plan should build mileage at a rate of around 10% per week, with long runs making up $\leq$ 30% of the total mileage. My plan incuded a taper that began approximately a week and a half before race day, so the load should drop off starting in Weeks 10-11.

    In terms of data visualization, this should look like a steady upward trend in load for the first 9-10 weeks, followed by a drop leading into race day.
    """)
    return


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
            avg_suffer_score=("suffer_score", "mean"),
            total_suffering=("suffer_score", "sum")
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

    rolling_km = weekly["total_km"].rolling(4, min_periods=1).mean()
    pct_change_km = weekly["total_km"].pct_change()

    ax1.plot(weekly["week_num"], rolling_km, color="#E8593C", linewidth=2, linestyle="--", label="4-week rolling avg")

    for i, (w, pct_km) in enumerate(zip(weekly["week_num"], pct_change_km)):
        if pct_km > 0.10:
            ax1.annotate(
                f"+{pct_km*100:.0f}%",
                xy=(w, weekly["total_km"].iloc[i]),
                xytext=(0, 6), textcoords="offset points",
                ha="center", fontsize=8, color="#E8593C",
            )

    ax1.set_xlabel("Week")
    ax1.set_ylabel("km")
    ax1.set_title("Weekly Mileage Volume")
    ax1.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax1.legend()
    ax1.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.gca()
    return (ax1,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Even with a few (expected) funky weeks, the training plan looks solid. However, mileage doesn't tell the whole story. I want to take a look at how difficult these runs were physiologically. Here's where Strava's "Suffer Score"– now called "Relative Effort"– comes in. Traditionally, I'd approach this kind of analysis by using max heart rate as a proxy for the strain of a given training session, then aggregate those values over each week of my plan. Relative Effort does this for me, accounting for the accumulation of effort over time and increased fitness during the training regimen. Let's see how my suffering stacks up over these 12 weeks. I'm going to call this metric my "Total Suffering".

    ## Suffer Score / Relative Effort
    """)
    return


@app.cell
def _(ax1, plt, ticker, weekly):
    fig2, ax2 = plt.subplots(figsize=(10, 4))

    ax2.bar(
        weekly["week_num"], weekly["total_suffering"],
        color="#FFA500", alpha=0.85, width=0.6, label="Weekly Suffering",
    )

    rolling_suf = weekly["total_suffering"].rolling(4, min_periods=1).mean()
    pct_change_suf = weekly["total_suffering"].pct_change()

    ax2.plot(weekly["week_num"], rolling_suf, color="#E8593C", linewidth=2, linestyle="--", label="4-week rolling avg")

    for j, (w2, pct) in enumerate(zip(weekly["week_num"], pct_change_suf)):
        if pct > 0.10:
            ax1.annotate(
                f"+{pct*100:.0f}%",
                xy=(w2, weekly["total_suffering"].iloc[j]),
                xytext=(0, 6), textcoords="offset points",
                ha="center", fontsize=8, color="#E8593C",
            )

    ax2.set_xlabel("Week")
    ax2.set_ylabel("Suffering")
    ax2.set_title("Weekly Suffering")
    ax2.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax2.legend()
    ax2.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.gca()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    These look tightly coupled, which is expected. Let's look at the correlation between some of these variables and determine where the biggest variance between total distance and total suffering comes in.
    """)
    return


@app.cell
def _(Patch, df, np, plt):
    suffer_df = df.dropna(subset=["suffer_score", "max_hr", "avg_hr"]).copy()

    # Combo index: z-score each predictor and sum them
    for col in ["distance_km", "max_hr", "elevation_m"]:
        suffer_df[f"z_{col}"] = (suffer_df[col] - suffer_df[col].mean()) / suffer_df[col].std()
    suffer_df["combo_index"] = suffer_df["z_distance_km"] + suffer_df["z_max_hr"] + suffer_df["z_elevation_m"]

    predictors = [
        ("distance_km", "Distance (km)"),
        ("max_hr", "Max HR (bpm)"),
        ("elevation_m", "Elevation (m)"),
        ("combo_index", "Combo index (z-scored sum)"),
    ]

    type_labels = {0: "Easy", 1: "Race", 2: "Long run", 3: "Workout/tempo"}
    type_colors = {0: "#4A90D9", 1: "#E8593C", 2: "#9B59B6", 3: "#F39C12"}

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes = axes.flatten()

    for ax, (col, label) in zip(axes, predictors):
        x = suffer_df[col]
        y = suffer_df["suffer_score"]

        colors = suffer_df["workout_type"].fillna(0).astype(int).map(type_colors).fillna("#4A90D9")
        ax.scatter(x, y, c=colors, alpha=0.8, edgecolors="none", s=60)

        mask = x.notna() & y.notna()
        z = np.polyfit(x[mask], y[mask], 1)
        r = np.corrcoef(x[mask], y[mask])[0, 1]
        xline = np.linspace(x.min(), x.max(), 100)
        ax.plot(xline, np.poly1d(z)(xline), color="#E8593C", linewidth=1.5, linestyle="--")

        ax.set_xlabel(label)
        ax.set_ylabel("Relative Effort")
        ax.set_title(f"Relative Effort vs {label}  (r = {r:.2f})")
        ax.spines[["top", "right"]].set_visible(False)

    # Legend — only show types that appear in the data
    present_types = suffer_df["workout_type"].fillna(0).astype(int).unique()
    legend_handles = [
        Patch(color=type_colors[t], label=type_labels[t])
        for t in sorted(present_types)
        if t in type_labels
    ]
    fig.legend(
        handles=legend_handles,
        title="Workout type",
        loc="lower center",
        ncol=len(legend_handles),
        bbox_to_anchor=(0.5, -0.04),
        frameon=False,
        fontsize=9,
        title_fontsize=9,
    )

    plt.suptitle("What drives Relative Effort?", fontsize=13, y=1.01)
    plt.tight_layout()
    plt.gca()
    return


@app.cell
def _(pd, plt, ticker, weekly):
    div = weekly.dropna(subset=["total_suffering"]).copy()

    div["z_km"] = (div["total_km"] - div["total_km"].mean()) / div["total_km"].std()
    div["z_suffering"] = (div["total_suffering"] - div["total_suffering"].mean()) / div["total_suffering"].std()

    # positive value = sufffered more despite shorter distance
    # negative value = suffered less despite longer distance
    div["divergence"] = div["z_suffering"] - div["z_km"]

    colors_ = ["#E8593C" if d > 0 else "#4A90D9" for d in div["divergence"]]

    fig3, ax3 = plt.subplots(figsize=(10, 4))

    bars = ax3.bar(div["week_num"], div["divergence"], color=colors_, alpha=0.85, width=0.6)
    ax3.axhline(0, color="var(--t)" if False else "grey", linewidth=0.8, linestyle="--")

    top2 = div.nlargest(2, "divergence")
    bot2 = div.nsmallest(2, "divergence")
    for _, row in pd.concat([top2, bot2]).iterrows():
        label_ = f"W{int(row['week_num'])}"
        yoff  = 0.08 if row["divergence"] > 0 else -0.14
        ax3.annotate(label_, xy=(row["week_num"], row["divergence"]),
                     xytext=(0, yoff * 60), textcoords="offset points",
                     ha="center", fontsize=8,
                     color="#E8593C" if row["divergence"] > 0 else "#4A90D9")

    ax3.set_xlabel("Week")
    ax3.set_ylabel("rel. effort − distance (z-score)")
    ax3.set_title("Distance vs. Relative Effort Divergence")
    ax3.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax3.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.gca()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    I'm somewhat surprised that Max HR and Suffer Score/Relative Effort has such a low correlation value, but it does make intuitive sense to me that total distance is the most significant contributor to those values.

    Now, let's review the divergence between distance and Relative Effort. After reviewing my training plan, I can clearly identify causes for some of the highest positive differences:
    - **Week 1**: The first week of training is always the hardest!
    - **Weeks 7-8**: Lots of sprint work, including hill sprints and a brutal 1 minute sprint x 10 repeat workout.
    - **Week 10**: Increased tempo work before the taper began.

    And for the biggest negative differences:
    - **Week 2**: I was running near the beaches in Baja California Sur, Mexico. Hard to get stressed in that environment!
    - **Week 5**: Honestly, I was just hyped up about the progress being made in my fitness. A (private) Instagram story confirms this! :)

    Sprints and tempo work have always been difficult for me. However, I know they are an integral part of building fitness, so I try my hardest to nail those workouts when they come up. The increased Relative Effort of that middle third of my training plan reflects the difficulty I faced with those sessions, but I truly believe they paid off on race day!
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Long Runs and Pace
    Long runs are [critical to any distance running training plan](https://www.fleetfeet.com/how-to-start-running/training-long-run?srsltid=AfmBOopQv63nH2RdzZt-vb-_y2iXwIPLWp9OtXSWKsEKNO-sYO1lEMv0). They build endurance by increasing VO2 Max, help prevent injury by gradually increasing weekly load, and contribute to mental toughness. All of these are key factors in training, and the quality and frequency of your long runs can make or break a half marathon race.

    Even though I was not perfectly consistent with my training plan, I made my best effort to *at least* complete my long run each week. My first long run was 10k, and I gradually increased distance as time passed. As mentioned earlier, long runs should make up $\leq$ 30% of the total distance run per week.

    I want to see how my average pace increased as a function of long runs completed, while examining the proportion of long run distance to total weekly distance. My average pace did improve over the training period, as I observed my "easy" runs landed at about 1 min/mile (or about 0.62 min/km) faster than I began, once all was said and done.
    """)
    return


@app.cell
def _(df, np, plt, weekly):
    long_runs = df[df["distance_km"] >= 10].copy()
    x_n = (df["date"] - df["date"].min()).dt.days.values

    long_runs = long_runs.merge(
        weekly[["week_num", "total_km"]], on="week_num", how="left"
    )
    long_runs["pct_of_week"] = (long_runs["distance_km"] / long_runs["total_km"] * 100).round(1)

    fig4, ax4 = plt.subplots(figsize=(10, 4))

    ax4.scatter(df["date"], df["pace_min_per_km"], alpha=0.4, color="#4A90D9", s=50, label="All runs")
    ax4.scatter(long_runs["date"], long_runs["pace_min_per_km"], color="#E8593C", s=80, zorder=5, label="long runs (≥10 km)")
    ax4.plot(df["date"], np.poly1d(np.polyfit(x_n, df["pace_min_per_km"].values, 1))(x_n), color="#2ecc71", linewidth=2, linestyle="--", label="Trend")

    pct_dists = []

    for _, row_ in long_runs.iterrows():
        ax4.annotate(
            f"{row_['pct_of_week']}%",
            xy=(row_["date"], row_["pace_min_per_km"]),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color="#E8593C",
        )
        pct_dists.append(row_['pct_of_week'])

    mean_pct_dist = round(sum(pct_dists) / len(pct_dists), 2)

    ax4.invert_yaxis()
    ax4.set_title("Pace progression over 12 weeks")
    ax4.set_xlabel("Date")
    ax4.set_ylabel("Pace (min/km)")
    ax4.legend()
    ax4.spines[["top", "right"]].set_visible(False)
    ax4.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.gca()
    return (mean_pct_dist,)


@app.cell(hide_code=True)
def _(mean_pct_dist, mo):
    mo.md(rf"""
    Yikes.. it looks like my long runs made up an average of {mean_pct_dist}% of my weekly distance. While I did steadily build my total distance and pace over the course of the training plan, I should definitely up my mid-week mileage next time to avoid overtraining on weekends.
    """)
    return


if __name__ == "__main__":
    app.run()
