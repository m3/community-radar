"""
CommunityRadar Flask Dashboard
Real-time community intelligence with time-series sentiment charts.

The application core: app creation, the JSON provider, the app-wide CSRF
hooks and client context processor, and blueprint registration. The routes
themselves live in the dashboard blueprint modules (views, api_analytics,
api_clients, api_engagement, api_intel, api_queue).
"""

from flask import Flask, jsonify, request
import os
import json
import sys
import secrets
from datetime import date, datetime

app = Flask(__name__)

# Register custom JSON provider to serialize datetime/date objects as ISO strings
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

try:
    from flask.json.provider import DefaultJSONProvider
    class CustomJSONProvider(DefaultJSONProvider):
        def dumps(self, obj, **kwargs):
            return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)
        def loads(self, s, **kwargs):
            return json.loads(s, **kwargs)
    app.json = CustomJSONProvider(app)
except ImportError:
    app.json_encoder = CustomJSONEncoder

# Re-exported for backwards compatibility with tests and external callers.
from src.dashboard.helpers import (
    ROOT,
    config_mgr,
    load_config,
    validate_client,
    get_db,
    int_arg,
    is_channel_owned,
    segment_filter,
    get_channel_segmentation,
    load_report,
    get_friendly_field_name,
    _calculate_engagement_score,
)

sys.path.insert(0, str(ROOT))


@app.context_processor
def inject_clients():
    """Inject available clients into all templates."""
    try:
        config = load_config()
        return dict(clients=config.get("clients", {}))
    except Exception:
        return dict(clients={})


@app.before_request
def csrf_protect():
    if app.config.get("TESTING"):
        return
    if request.method in ["POST", "PUT", "DELETE"]:
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            return jsonify({"success": False, "error": "CSRF Token missing or invalid"}), 403


@app.after_request
def set_csrf_cookie(response):
    if app.config.get("TESTING"):
        return response
    if not request.cookies.get("csrf_token"):
        token = secrets.token_urlsafe(32)
        response.set_cookie("csrf_token", token, httponly=False, samesite="Lax")
    return response


# ─── Blueprints ─────────────────────────────────────────────────────────
from src.dashboard.views import bp as views_bp
from src.dashboard.api_analytics import bp as analytics_bp
from src.dashboard.api_clients import bp as clients_api_bp
from src.dashboard.api_queue import bp as queue_bp
from src.dashboard.api_intel import bp as intel_bp
from src.dashboard.api_engagement import bp as engagement_bp

app.register_blueprint(views_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(clients_api_bp)
app.register_blueprint(queue_bp)
app.register_blueprint(intel_bp)
app.register_blueprint(engagement_bp)

# Under gunicorn run_dashboard() is never called, so enforce the non-superuser
# requirement at import when running in production (RADAR_REQUIRE_RLS set).
if os.getenv("RADAR_REQUIRE_RLS"):
    from src.db.session import warn_if_superuser
    warn_if_superuser()


def run_dashboard(client_name=None):
    """Launch the Flask development server.

    Debug mode is off unless FLASK_DEBUG is set — it leaks tracebacks with
    source and local variables to the caller. Deployments serve the `app`
    object under gunicorn instead (see docker-compose.yml).
    """
    from src.db.session import warn_if_superuser
    warn_if_superuser()
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("DASHBOARD_PORT", 5001))
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_dashboard()
