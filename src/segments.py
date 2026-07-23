"""Owned vs external channel classification.

Shared by the dashboard (live segment filtering) and the nightly analysis
job (precomputing per-segment stats) so both agree on what 'owned' means.
"""


def is_channel_owned(ch_name, owned_subreddits):
    """Whether a channel belongs to the client's owned community.

    Reddit channels named reddit-<sub>-* or reddit_<sub>_* are owned only when
    <sub> is in owned_subreddits. Non-reddit channels (Discord, etc.) are owned.
    """
    ch_name_lower = ch_name.lower()
    if ch_name_lower.startswith("reddit-"):
        parts = ch_name_lower.split("-")
        if len(parts) > 1 and parts[1].lower() in owned_subreddits:
            return True
        return False
    elif ch_name_lower.startswith("reddit_"):
        parts = ch_name_lower.split("_")
        if len(parts) > 1 and parts[1].lower() in owned_subreddits:
            return True
        return False
    elif not ch_name_lower.startswith("reddit"):
        return True
    return False


def owned_subreddits_for(client_config):
    """Set of lowercased subreddit names the client has marked as owned."""
    reddit_config = (client_config or {}).get("reddit", {}).get("subreddits", {}) or {}
    return {s.lower() for s, conf in reddit_config.items() if (conf or {}).get("owned")}
