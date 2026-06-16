try:
    from rapidfuzz import fuzz
except ImportError:
    import difflib
    class fuzz:
        @staticmethod
        def ratio(s1, s2):
            return difflib.SequenceMatcher(None, s1, s2).ratio() * 100

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
    for d_user in discord_users:
        d_name = d_user["username"].lower() if d_user.get("username") else ""
        if not d_name:
            continue
            
        for r_user in reddit_users:
            r_name = r_user["username"].lower() if r_user.get("username") else ""
            if not r_name:
                continue
                
            if d_name == r_name:
                matches.append({
                    "user_id": d_user["id"],
                    "platform1": "discord",
                    "username1": d_user["username"],
                    "platform2": "reddit",
                    "username2": r_user["username"],
                    "match_type": "exact",
                    "confidence": 1.0
                })
                continue
            
            score = fuzz.ratio(d_name, r_name)
            if score > 85:
                matches.append({
                    "user_id": d_user["id"],
                    "platform1": "discord",
                    "username1": d_user["username"],
                    "platform2": "reddit",
                    "username2": r_user["username"],
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
