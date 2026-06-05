"""
Competitor & Opportunity Analyzer
Scans r/billiards, r/snooker, and other niche subreddits for:
1. Pure Pool / Ripstone mentions (opportunity leads)
2. Competitor game mentions (market intelligence)
3. Unmet needs / feature requests
4. Sentiment around cue sports simulation
"""

import sqlite3
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

DB_PATH = Path("/Users/mathias/Development/community-radar/data/community_radar.db")
OUTPUT_PATH = Path("/Users/mathias/Development/community-radar/docs/competitor-opportunities.md")

# Brand & product names to track
BRAND_KEYWORDS = {
    "pure_pool": ["pure pool", "purepoolpro", "ripstone"],
    "competitor_games": [
        "virtual pool", "pool of eight", "side pocket", "snooker 19", "snooker 20",
        "wsc real", "matchroom pool", "8 ball pool", "miniclip", "foosball", "foos",
        "carom 3d", "vr pool", "pool vr", "killer pool", "archona", "snooker club",
    ],
    "cue_sports_general": [
        "billiards", "pool", "snooker", "8 ball", "9 ball", "10 ball", "carom",
        "straight pool", "one pocket", "bank pool", "trick shot", "trickshot",
    ],
    "game_features": [
        "physics", "realistic", "simulation", "tutorial", "training", "practice mode",
        "online multiplayer", "tournament", "ranked", "matchmaking", "replay", "stats",
    ],
    "pain_points": [
        "pay to win", "microtransactions", "ads", "laggy", "dead game", "abandoned",
        "no updates", "no support", "cheaters", "hackers", "toxic", "sweaty",
    ],
}


def search_keywords(text, keywords):
    """Return list of keywords found in text"""
    text_lower = text.lower()
    found = []
    for kw in keywords:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


def classify_message(text):
    """Classify message into opportunity/competitor/neutral"""
    brand_hits = search_keywords(text, BRAND_KEYWORDS["pure_pool"])
    competitor_hits = search_keywords(text, BRAND_KEYWORDS["competitor_games"])

    if brand_hits:
        return "pure_pool_mention", brand_hits
    elif competitor_hits:
        return "competitor_mention", competitor_hits
    return None, []


def extract_quote(text, keyword, context=200):
    """Extract quote around keyword"""
    text_lower = text.lower()
    idx = text_lower.find(keyword.lower())
    if idx == -1:
        return text[:300]

    start = max(0, idx - context)
    end = min(len(text), idx + len(keyword) + context)
    quote = text[start:end].strip()

    if start > 0:
        quote = "..." + quote
    if end < len(text):
        quote = quote + "..."
    return quote


def run_analysis():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    print("Loading Reddit messages from r/billiards and r/snooker...")
    # Get messages from billiards and snooker subreddits
    messages = db.execute("""
        SELECT m.message_id, m.content, m.timestamp, m.reactions, m.platform,
               c.name as channel_name
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        WHERE (c.name LIKE 'reddit-billiards%' OR c.name LIKE 'reddit-snooker%')
          AND m.content IS NOT NULL
          AND m.content != ''
        ORDER BY m.timestamp DESC
    """).fetchall()
    print(f"  {len(messages)} messages loaded")

    # Categorize
    pure_pool_mentions = []
    competitor_mentions = defaultdict(list)
    feature_requests = []
    pain_points = []
    sentiment_indicators = {"positive": 0, "negative": 0, "neutral": 0}

    for msg in messages:
        content = msg["content"]
        classification, hits = classify_message(content)

        # Track Pure Pool mentions
        if classification == "pure_pool_mention":
            for hit in hits:
                pure_pool_mentions.append({
                    "keyword": hit,
                    "channel": msg["channel_name"],
                    "timestamp": msg["timestamp"][:10] if msg["timestamp"] else "unknown",
                    "score": msg["reactions"] or 0,
                    "quote": extract_quote(content, hit),
                })

        # Track competitor mentions
        elif classification == "competitor_mention":
            for hit in hits:
                competitor_mentions[hit].append({
                    "channel": msg["channel_name"],
                    "timestamp": msg["timestamp"][:10] if msg["timestamp"] else "unknown",
                    "score": msg["reactions"] or 0,
                    "quote": extract_quote(content, hit),
                })

        # Feature requests
        feature_hits = search_keywords(content, BRAND_KEYWORDS["game_features"])
        if "suggestion" in content.lower() or "feature" in content.lower() or "wish" in content.lower() or "would be nice" in content.lower():
            if feature_hits:
                feature_requests.append({
                    "features": feature_hits,
                    "channel": msg["channel_name"],
                    "timestamp": msg["timestamp"][:10] if msg["timestamp"] else "unknown",
                    "quote": extract_quote(content, "suggestion" if "suggestion" in content.lower() else "feature"),
                })

        # Pain points
        pain_hits = search_keywords(content, BRAND_KEYWORDS["pain_points"])
        if pain_hits:
            pain_points.append({
                "pains": pain_hits,
                "channel": msg["channel_name"],
                "timestamp": msg["timestamp"][:10] if msg["timestamp"] else "unknown",
                "quote": extract_quote(content, pain_hits[0]),
                "score": msg["reactions"] or 0,
            })

        # Simple sentiment
        content_lower = content.lower()
        pos_words = ["love", "great", "amazing", "best", "awesome", "perfect", "recommend"]
        neg_words = ["hate", "terrible", "worst", "garbage", "trash", "awful", "disappointed"]
        if any(w in content_lower for w in pos_words):
            sentiment_indicators["positive"] += 1
        elif any(w in content_lower for w in neg_words):
            sentiment_indicators["negative"] += 1
        else:
            sentiment_indicators["neutral"] += 1

    db.close()

    # Generate report
    report = {
        "meta": {
            "total_messages_scanned": len(messages),
            "pure_pool_mentions": len(pure_pool_mentions),
            "competitor_mentions": sum(len(v) for v in competitor_mentions.values()),
            "unique_competitors": len(competitor_mentions),
            "feature_requests": len(feature_requests),
            "pain_points_flagged": len(pain_points),
        },
        "pure_pool_mentions": sorted(pure_pool_mentions, key=lambda x: -x["score"])[:25],
        "competitor_mentions": {
            comp: sorted(items, key=lambda x: -x["score"])[:5]
            for comp, items in sorted(competitor_mentions.items(), key=lambda x: -len(x[1]))[:10]
        },
        "feature_requests": feature_requests[:15],
        "pain_points": sorted(pain_points, key=lambda x: -x["score"])[:15],
        "sentiment_indicators": sentiment_indicators,
    }

    # Save JSON
    json_path = OUTPUT_PATH.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  JSON saved: {json_path}")

    # Generate Markdown
    md = generate_markdown(report)
    with open(OUTPUT_PATH, "w") as f:
        f.write(md)
    print(f"  Markdown saved: {OUTPUT_PATH}")

    return report


def generate_markdown(r):
    lines = []
    a = r
    m = a["meta"]

    lines.append("# Competitor & Opportunity Analysis")
    lines.append(f"\n*Scanned {m['total_messages_scanned']} messages from r/billiards + r/snooker*")
    lines.append(f"\n**Key findings:**")
    lines.append(f"- {m['pure_pool_mentions']} mentions of Pure Pool / Ripstone (opportunity leads)")
    lines.append(f"- {m['competitor_mentions']} mentions of {m['unique_competitors']} competitor games")
    lines.append(f"- {m['feature_requests']} feature requests identified")
    lines.append(f"- {m['pain_points_flagged']} pain point signals")

    # Sentiment
    s = a["sentiment_indicators"]
    total = sum(s.values())
    lines.append(f"\n## Community Sentiment (r/billiards + r/snooker)")
    lines.append(f"\n| Sentiment | Count | % |")
    lines.append(f"|-----------|-------|---|")
    for k, v in s.items():
        pct = v / total * 100 if total else 0
        lines.append(f"| {k.title()} | {v} | {pct:.1f}% |")

    # Pure Pool mentions
    lines.append(f"\n## 🎯 Pure Pool / Ripstone Mentions ({m['pure_pool_mentions']})")
    lines.append(f"\n*Highest-priority opportunity leads — people actively looking for/discussing our game*")
    if a["pure_pool_mentions"]:
        lines.append(f"\n| Date | Subreddit | Score | Quote |")
        lines.append(f"|------|-----------|-------|-------|")
        for mention in a["pure_pool_mentions"][:15]:
            sub = mention["channel"].split("-")[1] if "-" in mention["channel"] else mention["channel"]
            quote = mention["quote"].replace("\n", " ").replace("|", "\\|")[:200]
            lines.append(f"| {mention['timestamp']} | r/{sub} | {mention['score']} | {quote} |")
    else:
        lines.append(f"\n*No mentions found in scanned messages. This is itself a signal — Pure Pool is not on these users' radar.*")

    # Competitor mentions
    lines.append(f"\n## 🏆 Competitor Mentions ({m['unique_competitors']} games)")
    lines.append(f"\n*Market intelligence — what else are cue sports enthusiasts playing?*")
    if a["competitor_mentions"]:
        lines.append(f"\n| Competitor | Mentions | Top Quote |")
        lines.append(f"|------------|----------|-----------|")
        for comp, mentions in a["competitor_mentions"].items():
            top = mentions[0] if mentions else None
            if top:
                sub = top["channel"].split("-")[1] if "-" in top["channel"] else top["channel"]
                quote = top["quote"].replace("\n", " ").replace("|", "\\|")[:150]
                lines.append(f"| {comp.title()} | {len(mentions)} | r/{sub}: {quote} |")
    else:
        lines.append(f"\n*No competitor game mentions found.*")

    # Feature requests
    lines.append(f"\n## 💡 Feature Requests ({m['feature_requests']})")
    lines.append(f"\n*What users want — gaps we could fill*")
    if a["feature_requests"]:
        # Group by feature
        feature_counts = Counter()
        for req in a["feature_requests"]:
            for f in req["features"]:
                feature_counts[f] += 1

        lines.append(f"\n### Most Requested Features")
        lines.append(f"\n| Feature | Requests |")
        lines.append(f"|---------|----------|")
        for feat, count in feature_counts.most_common(15):
            lines.append(f"| {feat} | {count} |")

        lines.append(f"\n### Sample Quotes")
        for req in a["feature_requests"][:5]:
            sub = req["channel"].split("-")[1] if "-" in req["channel"] else req["channel"]
            quote = req["quote"].replace("\n", " ").replace("|", "\\|")[:200]
            features = ", ".join(req["features"])
            lines.append(f"\n> r/{sub} ({req['timestamp']}) — *{features}*")
            lines.append(f"> {quote}")
    else:
        lines.append(f"\n*No explicit feature requests captured.*")

    # Pain points
    lines.append(f"\n## 😤 Pain Points ({m['pain_points_flagged']})")
    lines.append(f"\n*What frustrates users about existing games — opportunity for differentiation*")
    if a["pain_points"]:
        pain_counts = Counter()
        for pp in a["pain_points"]:
            for p in pp["pains"]:
                pain_counts[p] += 1

        lines.append(f"\n### Most Common Pain Points")
        lines.append(f"\n| Pain Point | Mentions |")
        lines.append(f"|------------|----------|")
        for pain, count in pain_counts.most_common(10):
            lines.append(f"| {pain} | {count} |")

        lines.append(f"\n### Top Frustrations (by score)")
        for pp in a["pain_points"][:5]:
            sub = pp["channel"].split("-")[1] if "-" in pp["channel"] else pp["channel"]
            quote = pp["quote"].replace("\n", " ").replace("|", "\\|")[:200]
            pains = ", ".join(pp["pains"])
            lines.append(f"\n> r/{sub} ({pp['timestamp']}, score: {pp['score']}) — *{pains}*")
            lines.append(f"> {quote}")
    else:
        lines.append(f"\n*No pain point signals captured.*")

    # Strategic recommendations
    lines.append(f"\n## 🎯 Strategic Opportunities")
    lines.append(f"\n### Immediate (this week)")
    if a["pure_pool_mentions"]:
        lines.append(f"- **Engage with {len(a['pure_pool_mentions'])} Pure Pool mentions** — these are warm leads. Drop a helpful comment, link to relevant content.")
    if m["competitor_mentions"] > 0:
        top_competitor = max(a["competitor_mentions"].items(), key=lambda x: len(x[1]))[0] if a["competitor_mentions"] else None
        if top_competitor:
            lines.append(f"- **Monitor r/{top_competitor[0].replace('_', ' ')} mentions** — most-mentioned competitor. Consider what they're doing right/wrong.")

    lines.append(f"\n### Short-term (this month)")
    if a["feature_requests"]:
        top_feature = Counter()
        for req in a["feature_requests"]:
            for f in req["features"]:
                top_feature[f] += 1
        top = top_feature.most_common(1)[0]
        lines.append(f"- **Investigate top requested feature: {top[0]}** ({top[1]} requests) — could be a low-hanging fruit roadmap item.")

    lines.append(f"\n### Long-term (this quarter)")
    if a["pain_points"]:
        top_pain = Counter()
        for pp in a["pain_points"]:
            for p in pp["pains"]:
                top_pain[p] += 1
        top = top_pain.most_common(1)[0]
        lines.append(f"- **Address top pain point: {top[0]}** ({top[1]} mentions) — if Pure Pool avoids this issue, use it in marketing.")

    lines.append(f"\n### Brand Awareness Gap")
    if m["pure_pool_mentions"] < 5:
        lines.append(f"- **⚠️ Low Pure Pool awareness in r/billiards + r/snooker** — only {m['pure_pool_mentions']} mentions vs {m['competitor_mentions']} competitor mentions. Consider cross-posting content, AMAs, or community engagement strategy.")

    return "\n".join(lines)


if __name__ == "__main__":
    report = run_analysis()
    print("\n✅ Competitor analysis complete.")
