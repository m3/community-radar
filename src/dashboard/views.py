"""HTML page routes (server-rendered templates)."""

from flask import Blueprint, render_template

from src.dashboard.helpers import validate_client, load_config, load_report

bp = Blueprint("views", __name__)


@bp.route("/")
def hub():
    """Client selection hub."""
    return render_template("hub.html")


@bp.route("/clients")
def clients_hub():
    """Client management overview."""
    return render_template("clients.html")


@bp.route("/clients/<client_name>/edit")
def client_edit(client_name):
    """Form-based configuration editor for a specific client."""
    validate_client(client_name)
    config = load_config()
    client_config = config["clients"][client_name]
    return render_template("client_edit.html", client_name=client_name, config=client_config)


@bp.route("/<client_name>/dashboard")
def index(client_name):
    """Main dashboard page."""
    validate_client(client_name)
    report = load_report(client_name)
    return render_template("index.html", client_name=client_name, report=report)


@bp.route("/<client_name>/leaderboard")
def leaderboard(client_name):
    """Engagement leaderboard page."""
    validate_client(client_name)
    return render_template("leaderboard.html", client_name=client_name)


@bp.route("/<client_name>/user/<user_id>")
def user_profile(client_name, user_id):
    """User profile page."""
    validate_client(client_name)
    return render_template("user_profile.html", client_name=client_name, user_id=user_id)


@bp.route("/<client_name>/help")
def help_guide(client_name):
    """Serve the Mission Control Guide with client-specific context."""
    validate_client(client_name)
    return render_template("help.html", client_name=client_name)
