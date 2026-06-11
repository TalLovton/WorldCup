import logging
import os
import sys
from datetime import date, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not api_key:
        logger.error("FOOTBALL_DATA_API_KEY not set")
        sys.exit(1)

    from data.fetch import FootballDataClient, upsert_result, load_all_results
    from model.dixon_coles import fit, predict
    from news.summarize import fetch_news, get_discipline_notes
    from digest.send import build_digest, send_email

    client = FootballDataClient(api_key)

    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    # 1. Fetch yesterday's results and seed history
    logger.info("Fetching yesterday's results (%s)", yesterday)
    try:
        results = client.get_results(str(yesterday), str(yesterday))
        for m in results:
            upsert_result(m)
        logger.info("Stored %d result(s) from yesterday", len(results))
    except Exception as exc:
        logger.warning("Could not fetch yesterday's results: %s", exc)

    # 2. Fetch tomorrow's fixtures
    logger.info("Fetching tomorrow's fixtures (%s)", tomorrow)
    fixtures = []
    try:
        fixtures = client.get_fixtures(str(tomorrow), str(tomorrow))
        logger.info("Found %d fixture(s) for tomorrow", len(fixtures))
    except Exception as exc:
        logger.error("Could not fetch tomorrow's fixtures: %s", exc)

    # 3. No matches? Send a short note and exit
    if not fixtures:
        subject, body = build_digest(str(tomorrow), [], {}, [], [], [])
        send_email(subject, body)
        logger.info("No matches tomorrow — sent notification email.")
        return

    # 4. Fit Dixon-Coles
    history = load_all_results()
    logger.info("Fitting Dixon-Coles on %d historical matches", len(history))
    model_params = fit(history) if len(history) >= 5 else {}
    if not model_params:
        logger.warning("Too few history matches — predictions will use uniform prior")

    # 5. Predict each match
    predictions = {}
    for m in fixtures:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        key = f"{home} vs {away}"
        predictions[key] = predict(home, away, model_params)

    # 6. Scorers
    scorers = []
    try:
        scorers = client.get_scorers()
    except Exception as exc:
        logger.warning("Could not fetch scorers: %s", exc)

    # 7. News
    tomorrow_teams = []
    for m in fixtures:
        tomorrow_teams.append(m["homeTeam"]["name"])
        tomorrow_teams.append(m["awayTeam"]["name"])
    news_lines = fetch_news(tomorrow_teams)

    # 8. Discipline notes (from fixture data for tomorrow)
    discipline_notes = get_discipline_notes(fixtures)

    # 9. Build and send
    subject, body = build_digest(
        str(tomorrow), fixtures, predictions, scorers, news_lines, discipline_notes
    )
    send_email(subject, body)
    logger.info("Digest sent: %s", subject)


if __name__ == "__main__":
    main()
