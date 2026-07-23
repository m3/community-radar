"""Task queue routes: trigger, view, status, retry."""

from flask import Blueprint, render_template, jsonify

from src.dashboard.helpers import validate_client

bp = Blueprint("queue", __name__)


@bp.route("/api/<client_name>/trigger/<command>", methods=["POST"])
def api_trigger_task(client_name, command):
    """Trigger a background task for a client."""
    validate_client(client_name)
    if command not in ["collect", "analyze", "report"]:
        return jsonify({"success": False, "error": "Invalid command"}), 400

    from src.db.queue import enqueue_task
    # Enqueue with standard args
    enqueue_task(client_name, command, {"client": client_name})
    return jsonify({"success": True})


@bp.route("/queue")
def queue_view():
    return render_template("queue.html", client_name=None)


@bp.route("/api/queue/status")
def api_queue_status():
    from src.db.queue import get_queue_db
    db = get_queue_db()
    # Explicitly use text() to avoid wrapper issues if using LegacySessionWrapper
    from sqlalchemy import text
    tasks = db.session.execute(text("SELECT * FROM tasks ORDER BY id DESC LIMIT 50")).mappings().all()
    db.close()
    return jsonify([dict(t) for t in tasks])


@bp.route("/api/queue/retry/<int:task_id>", methods=["POST"])
def api_queue_retry(task_id):
    try:
        from src.db.queue import get_queue_db
        db = get_queue_db()
        db.execute("UPDATE tasks SET status='pending', error_log=NULL, started_at=NULL, finished_at=NULL WHERE id=?", (task_id,))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
