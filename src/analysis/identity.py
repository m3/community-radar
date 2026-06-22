try:
    from rapidfuzz import fuzz
except ImportError:
    import difflib
    class fuzz:
        @staticmethod
        def ratio(s1, s2):
            return difflib.SequenceMatcher(None, s1, s2).ratio() * 100

from collections import defaultdict

def match_identities(users):
    """
    Match identities between Discord and Reddit users based on username.
    
    Args:
        users: List of user dictionaries from the database.
               Expected keys: 'id', 'username', 'display_name'.
               Reddit users are assumed to have IDs starting with 'reddit_'.
    
    Returns:
        List of dictionaries suitable for the cross_references table.
    """
    discord_users = [u for u in users if not u["id"].startswith("reddit_")]
    reddit_users = [u for u in users if u["id"].startswith("reddit_")]
    
    matches = []
    matched_discord = set()
    matched_reddit = set()
    
    # 1. Exact matching (O(N + M))
    discord_by_username = {}
    for du in discord_users:
        uname = du.get("username")
        if uname:
            discord_by_username[uname.lower()] = du
            
    for ru in reddit_users:
        uname = ru.get("username")
        if uname and uname.lower() in discord_by_username:
            du = discord_by_username[uname.lower()]
            matches.append({
                "user_id": du["id"],
                "platform1": "discord",
                "username1": du["username"],
                "platform2": "reddit",
                "username2": ru["username"],
                "match_type": "exact",
                "confidence": 1.0
            })
            matched_discord.add(du["id"])
            matched_reddit.add(ru["id"])
            
    # 2. Fuzzy matching with 2-character blocking prefix
    unmatched_discord = [u for u in discord_users if u["id"] not in matched_discord]
    unmatched_reddit = [u for u in reddit_users if u["id"] not in matched_reddit]
    
    discord_blocks = defaultdict(list)
    for du in unmatched_discord:
        uname = du.get("username") or ""
        if uname:
            prefix = uname[:2].lower()
            discord_blocks[prefix].append(du)
            
    for ru in unmatched_reddit:
        uname = ru.get("username") or ""
        if uname:
            prefix = uname[:2].lower()
            block_users = discord_blocks.get(prefix, [])
            for du in block_users:
                d_name = du["username"].lower()
                r_name = ru["username"].lower()
                
                score = fuzz.ratio(d_name, r_name)
                if score > 85:
                    matches.append({
                        "user_id": du["id"],
                        "platform1": "discord",
                        "username1": du["username"],
                        "platform2": "reddit",
                        "username2": ru["username"],
                        "match_type": "fuzzy",
                        "confidence": score / 100.0
                    })
    return matches

def run_identity_sync(db):
    """
    Load all users from the users table.
    Call match_identities(users).
    Clear existing cross-references for this client and insert new matches.
    """
    cursor = db.execute("SELECT id, username, display_name FROM users")
    users = [dict(row) for row in cursor.fetchall()]
    
    matches = match_identities(users)
    
    # Clear existing matches for this client to avoid duplicates
    db.execute("DELETE FROM cross_references WHERE client_id = :client_id")
    
    for m in matches:
        db.execute("""
            INSERT INTO cross_references (
                client_id, user_id, platform1, username1, platform2, username2, match_type, confidence, created_at
            ) VALUES (:client_id, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            m["user_id"], m["platform1"], m["username1"],
            m["platform2"], m["username2"], m["match_type"], m["confidence"]
        ))
    db.commit()
