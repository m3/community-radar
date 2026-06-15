# Design Spec: Dynamic Tenant Routing & Client Hub

## 1. Overview
Transform the single-tenant dashboard into a multi-tenant web portal. This involves moving away from a fixed client configuration to a dynamic, URL-prefixed routing system.

## 2. Architecture
- **Routing:** All routes (except the root hub) will be prefixed with `/<client_name>/`.
- **State Management:** Tenancy is determined by the `client_name` path parameter, ensuring thread-safety and allowing multiple clients to be viewed simultaneously in different tabs.
- **Config Loading:** The dashboard will load `config.yaml` to discover available clients.
- **Data Access:** `load_report` and `get_db` will be refactored to accept a `client_name` parameter.

## 3. UI/UX Design
### 3.1 Client Hub (`/`)
- Entry point for the application.
- Grid of "Client Cards" showing client names and icons/logos (placeholders).
- Search bar to filter clients.

### 3.2 Layout (`layout.html`)
- **Sidebar:**
    - Professional, dark-themed sidebar.
    - Client branding/dropdown at the top.
    - Navigation links: Dashboard, Execution Queue (placeholder), Clients (back to hub).
- **Header:**
    - Current page title.
    - Search bar (optional for now).
- **Content Area:** 
    - Main viewport for child templates.

### 3.3 Dashboard (`index.html`)
- Refactored to extend `layout.html`.
- Displays client-specific sentiment and engagement data.

## 4. Components
### 4.1 Flask App (`app.py`)
- `hub()`: Renders `hub.html`.
- `index(client_name)`: Renders `index.html` with client data.
- API Routes: `/api/<client_name>/overview`, etc.

### 4.2 Database
- No changes to schema. Connection strings are derived from `client_name`.

## 5. Security & Validation
- Validate `client_name` against `config.yaml` on every request.
- Return 404 for unknown clients.

## 6. Success Criteria
- Navigating to `/` shows the client selection hub.
- Selecting a client takes the user to `/<client_name>/dashboard`.
- All dashboard data is correctly scoped to the selected client.
- Sidebar allows switching between clients or returning to the hub.
