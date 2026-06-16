# Design Spec: Linked Identity Visualization

Update the CommunityRadar dashboard to visualize linked identities for users, showing badges for cross-platform presence (e.g., Reddit) when a high-confidence match exists.

## User Experience
- When viewing a user profile, high-confidence linked identities will appear as badges in the header section.
- Badges will be color-coded by platform (Orange for Reddit, Indigo for others).
- Only matches with >80% confidence will be displayed.
- Badge format: `Also seen on [Platform] ([Username])`.

## Architecture

### Backend: `src/dashboard/app.py`
- Modify `api_cuebot_user_profile(client_name, user_id)`:
    - Query `cross_references` table for the given `user_id`.
    - Filter for `confidence > 0.8`.
    - Include `linked_identities` list in the JSON response.

### Frontend: `src/dashboard/templates/user_profile.html`
- Add `<div id="linkedIdentities" class="flex flex-wrap gap-2 mt-3"></div>` to the profile header.
- Update `renderProfile(data)` function:
    - Select the `#linkedIdentities` element.
    - Clear and re-populate it based on `data.linked_identities`.
    - Implement platform-specific styling.

## Data Flow
1. User navigates to `/user/<user_id>`.
2. Frontend calls `/api/.../cuebot/engagement/user/<user_id>`.
3. Backend fetches user details, message history, AND high-confidence cross-references.
4. Backend returns combined JSON.
5. Frontend renders user info and linked identity badges.

## Security & Performance
- Database query uses parameterized SQL to prevent injection.
- Filtering by confidence is done at the database level.
- `linked_identities` is an optional field in the response to maintain backward compatibility if needed.
