# Client Onboarding & Configuration Editor Design

**Status:** Draft
**Date:** 2026-06-14
**Topic:** Client Management UI & Persistence

## 1. Goal
Provide a user-friendly, form-based interface in the Web Portal to manage client configurations, allowing users to add new clients and update existing ones without manually editing `config.yaml`.

## 2. Architecture

### 2.1 Backend Persistence (`Option 1: Direct YAML Modification`)
- **Source of Truth:** `config.yaml` remains the single source of truth.
- **Config Manager:** A new module `src/dashboard/config_manager.py` will handle the logic for reading, merging, and writing the YAML file.
- **Atomic Operations:** 
    - Updates will be written to a temporary file (`config.yaml.tmp`) and then moved to `config.yaml` to prevent data loss on crash.
    - A backup (`config.yaml.bak`) will be created before any modification.
- **Library:** Use `PyYAML` with `sort_keys=False` and `default_flow_style=False` to maintain readability.

### 2.2 API Endpoints
- `GET /api/clients`: Returns all clients from the `clients` block in `config.yaml`.
- `POST /api/clients`: 
    - **Payload:** `{ "client_id": "new-client", "name": "New Client Name" }`
    - **Action:** Validates `client_id` (alphanumeric), adds empty skeleton to `clients` block, and saves.
- `POST /api/clients/<client_id>/update`:
    - **Payload:** Full client configuration block.
    - **Action:** Replaces the specific client's block in the global config and saves.

## 3. User Interface

### 3.1 Client Management Hub (`/clients`)
- **Layout:** Grid of cards extending `layout.html`.
- **Card Elements:**
    - Client Name & ID.
    - Summary of configured collectors (e.g., "3 Subreddits, 2 Discord Servers").
    - "Manage" button linking to `/clients/<client_id>/edit`.
- **Add Client Modal:** A simple modal triggered by an "Add Client" card at the end of the grid.

### 3.2 Form-Based Editor (`/clients/<client_id>/edit`)
- **Structure:** Tabbed interface (General, Reddit, Discord, Domains).
- **Dynamic Fields:**
    - Uses JavaScript to allow adding/removing items in lists:
        - Subreddits list (with sort selections).
        - Track keywords for subreddits.
        - Discord server IDs and channel mappings.
        - Domain monitoring lists.
- **Validation:** Client-side validation for required fields and basic formats.

## 4. Implementation Details

### 4.1 Config Manager Functions
- `load_full_config()`: Returns the entire `config.yaml` as a dict.
- `save_full_config(config_dict)`: Safely writes the dict back to YAML.
- `get_client_config(client_id)`: Helper to get a specific block.
- `update_client_config(client_id, new_data)`: Helper to merge and save.

### 4.2 Template Files
- `src/dashboard/templates/clients.html`: The hub/grid view.
- `src/dashboard/templates/client_edit.html`: The form-based editor.

## 5. Testing Strategy
- **Unit Tests:** Test `config_manager.py` for correct YAML round-tripping and error handling for malformed files.
- **Integration Tests:** Test the API endpoints with mock config files.
- **Manual Verification:** Add a test client via the UI and verify `config.yaml` is updated correctly.

## 6. Success Criteria
1.  Users can add a new client through the UI.
2.  Users can add/remove subreddits or discord channels for an existing client.
3.  The `config.yaml` file remains readable and valid after UI edits.
4.  All changes are immediately reflected in the CLI (e.g., `python src/main.py status --client <new-client>`).
