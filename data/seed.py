"""
Seed history.db with past World Cup results (2018, 2022).
Run once locally or automatically on first run via main.py.
"""
import logging
import time
import os
import sys

logger = logging.getLogger(__name__)

PAST_SEASONS = [2018, 2022]


def is_seeded() -> bool:
    from data.fetch import get_db
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    conn.close()
    return count > 0


def seed(api_key: str) -> int:
    from data.fetch import FootballDataClient, upsert_result, COMPETITION
    client = FootballDataClient(api_key)
    total = 0
    for season in PAST_SEASONS:
        logger.info("Seeding WC %d results...", season)
        try:
            data = client._get(
                f"/competitions/{COMPETITION}/matches",
                {"season": season, "status": "FINISHED"},
            )
            matches = data.get("matches", [])
            for m in matches:
                upsert_result(m)
            logger.info("  Stored %d matches from WC %d", len(matches), season)
            total += len(matches)
            time.sleep(1)
        except Exception as exc:
            logger.warning("Could not fetch WC %d: %s", season, exc)
    logger.info("Seeding complete — %d total matches stored", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not api_key:
        print("FOOTBALL_DATA_API_KEY not set")
        sys.exit(1)
    seed(api_key)
