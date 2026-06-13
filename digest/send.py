import os
import smtplib
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment

logger = logging.getLogger(__name__)

IL_TZ = ZoneInfo("Asia/Jerusalem")

GREEN = {"bg": "#EAF3DE", "text": "#3B6D11"}
RED   = {"bg": "#FCEBEB", "text": "#A32D2D"}

_TEMPLATE = """\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F7F6F2;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#FFFFFF;border:1px solid #E5E5E0;border-radius:12px;overflow:hidden;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

  <tr><td>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td width="33%" height="6" style="background:#639922;font-size:0;line-height:0;">&nbsp;</td>
      <td width="34%" height="6" style="background:#378ADD;font-size:0;line-height:0;">&nbsp;</td>
      <td width="33%" height="6" style="background:#E24B4A;font-size:0;line-height:0;">&nbsp;</td>
    </tr></table>
  </td></tr>

  <tr><td style="padding:24px 24px 8px;">
    <div style="font-size:20px;font-weight:500;color:#1A1A1A;">World cup 2026 — daily digest</div>
    <div style="font-size:13px;color:#6B6B6B;padding-top:2px;">{{ digest_date }}</div>
  </td></tr>

  {% if matches %}
  <tr><td style="padding:12px 24px 4px;font-size:12px;color:#6B6B6B;letter-spacing:.04em;">Tomorrow's matches</td></tr>

  {% for m in matches %}
  <tr><td style="padding:8px 24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #E5E5E0;border-radius:8px;">
      <tr><td style="padding:14px 14px 0;">
        <div style="font-size:18px;font-weight:500;color:#1A1A1A;">{{ m.home }} vs {{ m.away }}</div>
        <div style="font-size:13px;color:#6B6B6B;padding:4px 0 12px;">{{ m.kickoff_israel }} Israel · {{ m.stage }} · {{ m.venue }}</div>
      </td></tr>
      <tr><td style="padding:0 14px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
          <td width="33%" align="center" style="background:{{ m.home_bg }};border-radius:8px;padding:10px 4px;">
            <div style="font-size:12px;color:{{ m.home_text }};">{{ m.home }}</div>
            <div style="font-size:17px;font-weight:500;color:{{ m.home_text }};">{{ m.p_home }}%</div></td>
          <td width="6"></td>
          <td width="33%" align="center" style="background:#E6F1FB;border-radius:8px;padding:10px 4px;">
            <div style="font-size:12px;color:#185FA5;">Draw</div>
            <div style="font-size:17px;font-weight:500;color:#185FA5;">{{ m.p_draw }}%</div></td>
          <td width="6"></td>
          <td width="33%" align="center" style="background:{{ m.away_bg }};border-radius:8px;padding:10px 4px;">
            <div style="font-size:12px;color:{{ m.away_text }};">{{ m.away }}</div>
            <div style="font-size:17px;font-weight:500;color:{{ m.away_text }};">{{ m.p_away }}%</div></td>
        </tr></table>
      </td></tr>
      <tr><td style="padding:14px 14px 0;">
        <table role="presentation" width="100%" style="border-top:1px solid #E5E5E0;font-size:14px;"><tr>
          <td style="color:#6B6B6B;padding:8px 0;">Most likely score</td>
          <td align="right" style="font-weight:500;color:#1A1A1A;padding:8px 0;">{{ m.most_likely }}</td>
        </tr></table>
        <div style="font-size:13px;color:#6B6B6B;padding:4px 0;">Likely scorelines</div>
        <div style="padding-bottom:6px;">
          {% for s in m.scorelines %}<span style="display:inline-block;font-size:12px;color:#6B6B6B;background:#F1EFE8;border-radius:12px;padding:3px 9px;margin:0 4px 4px 0;">{{ s.score }} · {{ s.pct }}%</span>{% endfor %}
        </div>
        <table role="presentation" width="100%" style="border-top:1px solid #E5E5E0;font-size:14px;"><tr>
          <td style="color:#6B6B6B;padding:8px 0;">Clean sheet</td>
          <td align="right" style="color:#1A1A1A;padding:8px 0;">{{ m.home }} {{ m.cs_home }}% · {{ m.away }} {{ m.cs_away }}%</td>
        </tr></table>
        {% if m.note %}<div style="font-size:12px;color:#9B9B9B;padding:0 0 14px;">{{ m.note }}</div>{% endif %}
      </td></tr>
    </table>
  </td></tr>
  {% endfor %}
  {% else %}
  <tr><td style="padding:16px 24px;font-size:14px;color:#6B6B6B;">No matches scheduled tomorrow.</td></tr>
  {% endif %}

  {% if standings %}
  <tr><td style="padding:12px 24px 4px;font-size:12px;color:#6B6B6B;letter-spacing:.04em;">Group standings</td></tr>
  {% for group in standings %}
  <tr><td style="padding:4px 24px 8px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #E5E5E0;border-radius:8px;">
      <tr><td style="padding:10px 14px 6px;">
        <div style="font-size:13px;font-weight:500;color:#1A1A1A;">{{ group.group }}</div>
      </td></tr>
      <tr><td style="padding:0 14px 10px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;border-collapse:collapse;">
          <tr style="color:#9B9B9B;border-bottom:1px solid #E5E5E0;">
            <td style="padding:4px 0;">Team</td>
            <td align="center" style="padding:4px 4px;">P</td>
            <td align="center" style="padding:4px 4px;">W</td>
            <td align="center" style="padding:4px 4px;">D</td>
            <td align="center" style="padding:4px 4px;">L</td>
            <td align="center" style="padding:4px 4px;">GF</td>
            <td align="center" style="padding:4px 4px;">GA</td>
            <td align="center" style="padding:4px 4px;">GD</td>
            <td align="center" style="padding:4px 0;font-weight:500;">Pts</td>
          </tr>
          {% for row in group.table %}
          <tr style="border-bottom:1px solid #F1EFE8;color:#1A1A1A;">
            <td style="padding:5px 0;">{{ row.team }}</td>
            <td align="center" style="padding:5px 4px;color:#6B6B6B;">{{ row.played }}</td>
            <td align="center" style="padding:5px 4px;color:#6B6B6B;">{{ row.won }}</td>
            <td align="center" style="padding:5px 4px;color:#6B6B6B;">{{ row.drawn }}</td>
            <td align="center" style="padding:5px 4px;color:#6B6B6B;">{{ row.lost }}</td>
            <td align="center" style="padding:5px 4px;color:#6B6B6B;">{{ row.gf }}</td>
            <td align="center" style="padding:5px 4px;color:#6B6B6B;">{{ row.ga }}</td>
            <td align="center" style="padding:5px 4px;color:#6B6B6B;">{{ "%+d" % row.gd }}</td>
            <td align="center" style="padding:5px 0;font-weight:500;">{{ row.points }}</td>
          </tr>
          {% endfor %}
        </table>
      </td></tr>
    </table>
  </td></tr>
  {% endfor %}
  {% endif %}

  <tr><td style="padding:12px 24px 4px;font-size:12px;color:#6B6B6B;letter-spacing:.04em;">Key news</td></tr>
  <tr><td style="padding:0 24px 8px;font-size:14px;color:#1A1A1A;">{{ news_summary or "No relevant news found for tomorrow's teams." }}</td></tr>

  <tr><td style="padding:12px 24px 4px;font-size:12px;color:#6B6B6B;letter-spacing:.04em;">Discipline notes</td></tr>
  <tr><td style="padding:0 24px 16px;font-size:14px;color:#1A1A1A;">{{ discipline_note or "No confirmed suspensions from data." }}</td></tr>

  <tr><td style="padding:14px 24px;background:#F7F6F2;border-top:1px solid #E5E5E0;font-size:12px;color:#9B9B9B;line-height:1.6;">
    Predictions are model probabilities, not guarantees. Injuries and suspensions are reported from official data only.
  </td></tr>

</table>
</td></tr>
</table>
"""


def _utc_to_israel(utc_str: str) -> str:
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        return dt.astimezone(IL_TZ).strftime("%H:%M")
    except Exception:
        return utc_str


def _build_match_ctx(fixture: dict, pred: dict) -> dict:
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]

    p_home = round((pred.get("home_win") or 0) * 100, 1) if pred else 33.3
    p_draw = round((pred.get("draw") or 0) * 100, 1) if pred else 33.3
    p_away = round((pred.get("away_win") or 0) * 100, 1) if pred else 33.3

    if p_home >= p_away:
        home_bg, home_text = GREEN["bg"], GREEN["text"]
        away_bg, away_text = RED["bg"], RED["text"]
    else:
        home_bg, home_text = RED["bg"], RED["text"]
        away_bg, away_text = GREEN["bg"], GREEN["text"]

    scorelines = []
    if pred:
        sorted_scores = sorted(
            pred.get("score_probs", {}).items(), key=lambda x: x[1], reverse=True
        )[:6]
        scorelines = [{"score": s, "pct": round(p * 100, 1)} for s, p in sorted_scores]

    cs_home = round((pred.get("clean_sheet_home") or 0) * 100, 1) if pred else None
    cs_away = round((pred.get("clean_sheet_away") or 0) * 100, 1) if pred else None

    return {
        "home": home,
        "away": away,
        "kickoff_israel": _utc_to_israel(fixture.get("utcDate", "")),
        "venue": fixture.get("venue", "TBC"),
        "stage": fixture.get("stage", "").replace("_", " ").title(),
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "home_bg": home_bg,
        "home_text": home_text,
        "away_bg": away_bg,
        "away_text": away_text,
        "most_likely": pred.get("most_likely_score", "N/A") if pred else "N/A",
        "scorelines": scorelines,
        "cs_home": cs_home,
        "cs_away": cs_away,
        "note": (pred.get("note") or "") if pred else "",
    }


def build_digest(
    tomorrow_date: str,
    fixtures: list[dict],
    predictions: dict,
    scorers: list[dict],
    news_lines: list[str],
    discipline_notes: list[str],
    standings: list[dict] = None,
) -> tuple[str, str]:
    matches = []
    for m in fixtures:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        pred = predictions.get(f"{home} vs {away}")
        matches.append(_build_match_ctx(m, pred))

    news_summary = "<br>".join(news_lines) if news_lines else ""
    discipline_note = "<br>".join(discipline_notes) if discipline_notes else ""

    env = Environment(autoescape=True)
    template = env.from_string(_TEMPLATE)
    body = template.render(
        digest_date=tomorrow_date,
        matches=matches,
        standings=standings or [],
        news_summary=news_summary,
        discipline_note=discipline_note,
    )

    if not fixtures:
        subject = f"WC 2026 Digest — No matches tomorrow"
    else:
        count = len(fixtures)
        subject = f"WC 2026 Digest — {tomorrow_date} ({count} match{'es' if count != 1 else ''})"

    return subject, body


def send_email(subject: str, body: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("RECIPIENT_EMAIL", gmail_user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg.attach(MIMEText(body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipient, msg.as_string())

    logger.info("Email sent to %s: %s", recipient, subject)
