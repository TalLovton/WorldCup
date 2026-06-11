import os
import smtplib
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

IL_TZ = ZoneInfo("Asia/Jerusalem")


def _utc_to_israel(utc_str: str) -> str:
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        il = dt.astimezone(IL_TZ)
        return il.strftime("%H:%M (Israel)")
    except Exception:
        return utc_str


def _pct(v) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.1f}%"


def build_digest(
    tomorrow_date: str,
    fixtures: list[dict],
    predictions: dict,
    scorers: list[dict],
    news_lines: list[str],
    discipline_notes: list[str],
) -> tuple[str, str]:
    lines = []
    lines.append(f"WORLD CUP 2026 DAILY DIGEST — {tomorrow_date}")
    lines.append("=" * 60)

    if not fixtures:
        lines.append("")
        lines.append("No matches scheduled tomorrow.")
        body = "\n".join(lines)
        return "WC 2026 Digest — No matches tomorrow", body

    lines.append("")
    lines.append("TOMORROW'S MATCHES")
    lines.append("-" * 40)

    for m in fixtures:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        kickoff = _utc_to_israel(m.get("utcDate", ""))
        venue = m.get("venue", "TBC")
        stage = m.get("stage", "")
        lines.append(f"\n{home} vs {away}")
        lines.append(f"  Kickoff : {kickoff}")
        lines.append(f"  Venue   : {venue}")
        lines.append(f"  Stage   : {stage}")

        key = f"{home} vs {away}"
        pred = predictions.get(key)
        if pred:
            lines.append(f"  Prediction : {home} win {_pct(pred['home_win'])}  |  "
                         f"Draw {_pct(pred['draw'])}  |  {away} win {_pct(pred['away_win'])}")
            lines.append(f"  Most likely score : {pred['most_likely_score']}")
            cs_h = _pct(pred.get("clean_sheet_home"))
            cs_a = _pct(pred.get("clean_sheet_away"))
            lines.append(f"  Clean sheet : {home} {cs_h}  |  {away} {cs_a}")
            if pred.get("note"):
                lines.append(f"  Note : {pred['note']}")

    if scorers:
        lines.append("")
        lines.append("TOURNAMENT TOP SCORER")
        lines.append("-" * 40)
        top = scorers[0]
        player = top.get("player", {}).get("name", "Unknown")
        team = top.get("team", {}).get("name", "")
        goals = top.get("goals", 0)
        lines.append(f"{player} ({team}) — {goals} goal{'s' if goals != 1 else ''}")

    lines.append("")
    lines.append("KEY NEWS")
    lines.append("-" * 40)
    for nl in news_lines:
        lines.append(nl)

    lines.append("")
    lines.append("DISCIPLINE NOTES")
    lines.append("-" * 40)
    for dn in discipline_notes:
        lines.append(dn)

    lines.append("")
    lines.append("─" * 60)
    lines.append("Predictions are model probabilities, not guarantees.")
    lines.append("Injuries/suspensions are reported from official data only.")

    body = "\n".join(lines)
    subject = f"WC 2026 Digest — {tomorrow_date} ({len(fixtures)} match{'es' if len(fixtures) != 1 else ''})"
    return subject, body


def send_email(subject: str, body: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("RECIPIENT_EMAIL", gmail_user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipient, msg.as_string())

    logger.info("Email sent to %s: %s", recipient, subject)
