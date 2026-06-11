"""
Seed history.db with WC 2018 & 2022 results from bundled JSON.
Runs automatically on first run via main.py when history.db is empty.
"""
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "wc_history.json")


def _get_db():
    try:
        from data.fetch import get_db
    except ModuleNotFoundError:
        from fetch import get_db
    return get_db()


def is_seeded() -> bool:
    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    conn.close()
    return count > 0


def seed() -> int:
    conn = _get_db()
    with open(HISTORY_FILE) as f:
        matches = json.load(f)
    for i, m in enumerate(matches):
        conn.execute(
            """
            INSERT INTO matches (match_id, home_team, away_team, home_goals, away_goals, match_date, stage)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(match_id) DO NOTHING
            """,
            (
                f"static_{m['season']}_{i}",
                m["home"],
                m["away"],
                m["home_goals"],
                m["away_goals"],
                f"{m['season']}-01-01",
                "HISTORICAL",
            ),
        )
    conn.commit()
    conn.close()
    logger.info("Seeded %d historical matches into history.db", len(matches))
    return len(matches)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
    seed()
    print("Done.")
