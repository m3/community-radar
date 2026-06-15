# Design Spec: Highlight External Mentions in Raw Messages API

## Purpose
Enhance the `api_raw_messages` endpoint to identify messages from external Reddit communities that mention specific tracked keywords. This allows the dashboard to highlight these messages for better market awareness.

## Architecture
The flagging logic will be implemented as a post-processing step in the Flask API endpoint. After retrieving message rows from the database, the server will check each message against the client's configuration.

## Data Flow
1.  **Endpoint Called:** `/api/<client_name>/raw_messages`
2.  **Config Loading:** Load `config.yaml` using `config_mgr.load()`.
3.  **Keyword Extraction:**
    *   Navigate to `clients[client_name]['reddit']['subreddits']`.
    *   Identify subreddits that have `track_keywords`.
    *   Collect all such keywords into a flat list.
    *   Generate a list of channel prefixes: `reddit_<subreddit_name_lowercase>`.
4.  **Database Query:** Execute existing SQL query to fetch raw messages.
5.  **Post-Processing:**
    *   Iterate through each row.
    *   Set `is_external_mention = False` by default.
    *   Check if `channel_name.lower()` starts with any of the identified prefixes.
    *   Check if `content.lower()` contains any of the identified keywords.
    *   If both match, set `is_external_mention = True`.
6.  **Response:** Return the enriched list of message dictionaries.

## Implementation Details
*   File: `src/dashboard/app.py`
*   Function: `api_raw_messages(client_name)`
*   Logic uses case-insensitive matching for both prefixes and keywords.
*   Handles potential `None` or empty values for content and channel name.

## Success Criteria
*   The API returns a JSON list of messages.
*   Each message object contains the `is_external_mention` key.
*   Messages from tracked subreddits (e.g., `reddit_billiards`) containing tracked keywords (e.g., `pure pool`) have `is_external_mention: true`.
*   All other messages have `is_external_mention: false`.
