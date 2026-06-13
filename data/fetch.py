import os
import sqlite3
import time
import logging
from datetime import datetime, timezone
import requests

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "history.db")
BASE_URL = "https://api.football-data.org/v4"
COMPETITION = "WC"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            match_id TEXT UNIQUE,
            home_team TEXT,
            away_team TEXT,
            home_goals INTEGER,
            away_goals INTEGER,
            match_date TEXT,
            stage TEXT
        )
    """)
    conn.commit()
    return conn


class FootballDataClient:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({"X-Auth-Token": api_key})
        self._last_call = 0.0

    def _get(self, path: str, params: dict = None) -> dict:
        elapsed = time.time() - self._last_call
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        for attempt in range(4):
            resp = self.session.get(f"{BASE_URL}{path}", params=params, timeout=15)
            self._last_call = time.time()
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = 6 * (2 ** attempt)
                logger.warning("Rate limited; waiting %ss", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
        raise RuntimeError("Exceeded retries for " + path)

    def get_fixtures(self, date_from: str, date_to: str) -> list[dict]:
        data = self._get(
            f"/competitions/{COMPETITION}/matches",
            {"dateFrom": date_from, "dateTo": date_to, "status": "SCHEDULED,TIMED,IN_PLAY"},
        )
        return data.get("matches", [])

    def get_results(self, date_from: str, date_to: str) -> list[dict]:
        data = self._get(
            f"/competitions/{COMPETITION}/matches",
            {"dateFrom": date_from, "dateTo": date_to, "status": "FINISHED"},
        )
        return data.get("matches", [])

    def get_scorers(self) -> list[dict]:
        data = self._get(f"/competitions/{COMPETITION}/scorers", {"limit": 10})
        return data.get("scorers", [])

    def get_standings(self) -> list[dict]:
        data = self._get(f"/competitions/{COMPETITION}/standings")
        groups = []
        for standing in data.get("standings", []):
            if standing.get("type") != "TOTAL":
                continue
            group_name = standing.get("group", "").replace("GROUP_", "Group ")
            rows = []
            for entry in standing.get("table", []):
                rows.append({
                    "team": entry["team"]["name"],
                    "played": entry["playedGames"],
                    "won": entry["won"],
                    "drawn": entry["draw"],
                    "lost": entry["lost"],
                    "gf": entry["goalsFor"],
                    "ga": entry["goalsAgainst"],
                    "gd": entry["goalDifference"],
                    "points": entry["points"],
                })
            groups.append({"group": group_name, "table": rows})
        return groups


def upsert_result(match: dict) -> None:
    score = match.get("score", {}).get("fullTime", {})
    home_goals = score.get("home")
    away_goals = score.get("away")
    if home_goals is None or away_goals is None:
        return
    conn = get_db()
    conn.execute(
        """
        INSERT INTO matches (match_id, home_team, away_team, home_goals, away_goals, match_date, stage)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id) DO UPDATE SET
            home_goals=excluded.home_goals,
            away_goals=excluded.away_goals
        """,
        (
            str(match["id"]),
            match["homeTeam"]["name"],
            match["awayTeam"]["name"],
            home_goals,
            away_goals,
            match.get("utcDate", ""),
            match.get("stage", ""),
        ),
    )
    conn.commit()
    conn.close()


def load_all_results() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT home_team, away_team, home_goals, away_goals FROM matches"
    ).fetchall()
    conn.close()
    return [
        {"home": r[0], "away": r[1], "home_goals": r[2], "away_goals": r[3]}
        for r in rows
    ]
