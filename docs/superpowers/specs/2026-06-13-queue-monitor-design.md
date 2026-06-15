# Real-time Queue Monitor UI Design

## Purpose
Provide a web-based UI to monitor background task execution, view status, and retry failed tasks.

## Components

### Backend (src/dashboard/app.py)
- `/queue`: Global route to render the queue management page.
- `/api/queue/status`: Returns JSON list of the 50 most recent tasks from `data/queue.db`.
- `/api/queue/retry/<task_id>`: Endpoint to reset a task status to 'pending' to trigger a retry.

### Frontend (src/dashboard/templates/queue.html)
- Extends `layout.html`.
- Displays a table of tasks with columns: ID, Client, Command, Status, Created At, and Actions.
- Status column should have visual indicators (e.g., badges for pending, running, completed, failed).
- "Retry" button for tasks that have failed or completed.
- JavaScript `setInterval` fetches status every 5 seconds and updates the table.

## Data Flow
1. User navigates to `/queue`.
2. Browser fetches initial data from `/api/queue/status`.
3. Every 5 seconds, browser re-fetches data.
4. User clicks "Retry" → POST to `/api/queue/retry/<id>` → Page refreshes or table updates.

## UI Design
- Dark mode consistent with existing dashboard.
- Tailwind CSS for styling.
- FontAwesome icons for status/actions.

## Verification Plan
- Manually verify `/queue` page loads.
- Manually verify API returns data.
- Verify retry button updates database status.
