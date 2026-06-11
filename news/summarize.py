import os
import logging
import feedparser

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.skysports.com/rss/12040",  # Sky Sports football
]


def _contains_team(text: str, teams: list[str]) -> bool:
    text_lower = text.lower()
    return any(t.lower() in text_lower for t in teams)


def _first_sentences(text: str, n: int = 2) -> str:
    sentences = []
    for part in text.replace(".", ".|").split("|"):
        part = part.strip()
        if part:
            sentences.append(part)
        if len(sentences) >= n:
            break
    return " ".join(sentences)


def _gemini_summarize(articles: list[dict], teams: list[str]) -> list[str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        bullet_list = "\n".join(
            f"- {a['title']}: {a['summary'][:300]}" for a in articles[:10]
        )
        prompt = (
            f"Summarise the following football news relevant to these teams: {', '.join(teams)}.\n"
            f"Return 3-5 concise bullet points in English, focusing on injuries, suspensions, form, "
            f"or anything that could affect match outcomes.\n\n{bullet_list}"
        )
        response = model.generate_content(prompt)
        return [response.text]
    except Exception as exc:
        logger.warning("Gemini summarization failed: %s", exc)
        return []


def fetch_news(teams: list[str]) -> list[str]:
    relevant = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                if _contains_team(title + " " + summary, teams):
                    relevant.append({"title": title, "summary": summary})
        except Exception as exc:
            logger.warning("RSS fetch failed for %s: %s", url, exc)

    if not relevant:
        return ["No relevant news found for tomorrow's teams."]

    if os.environ.get("GEMINI_API_KEY"):
        result = _gemini_summarize(relevant, teams)
        if result:
            return result

    # Fallback: plain headlines + first sentences
    lines = []
    seen = set()
    for a in relevant[:6]:
        key = a["title"][:60]
        if key not in seen:
            seen.add(key)
            snippet = _first_sentences(a["summary"])
            lines.append(f"- {a['title']}. {snippet}")
    return lines


def get_discipline_notes(matches: list[dict]) -> list[str]:
    notes = []
    for m in matches:
        home = m.get("homeTeam", {}).get("name", "")
        away = m.get("awayTeam", {}).get("name", "")
        bookings = m.get("bookings", [])
        red_cards = [b for b in bookings if b.get("card") == "RED_CARD"]
        for rc in red_cards:
            player = rc.get("player", {}).get("name", "Unknown")
            team = rc.get("team", {}).get("name", "")
            notes.append(f"Suspension: {player} ({team}) — red card, likely suspended.")
    if not notes:
        notes.append("No confirmed suspensions from API data.")
    return notes
