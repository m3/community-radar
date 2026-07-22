"""Client CRUD routes: list, create, and update client configuration."""

from flask import Blueprint, jsonify, request

from src.dashboard.helpers import config_mgr, validate_client, get_friendly_field_name

bp = Blueprint("clients_api", __name__)


@bp.route("/api/clients")
def api_get_clients():
    """Return all clients."""
    config = config_mgr.load()
    return jsonify({"clients": config.get("clients", {})})


@bp.route("/api/clients", methods=["POST"])
def api_create_client():
    """Create a new client."""
    data = request.json
    client_id = data.get("client_id")
    name = data.get("name")

    if not client_id or not all(c.isalnum() or c in "-_" for c in client_id):
        return jsonify({"success": False, "error": "Invalid client_id"}), 400

    config = config_mgr.load()
    if client_id in config.get("clients", {}):
        return jsonify({"success": False, "error": "Client already exists"}), 400

    config.setdefault("clients", {})[client_id] = {
        "name": name,
        "reddit": {"subreddits": {}},
        "discord": {"servers": {}}
    }
    config_mgr.save(config)
    return jsonify({"success": True})


@bp.route("/api/clients/<client_name>/update", methods=["POST"])
def api_update_client_config(client_name):
    """Update an existing client's configuration with basic validation."""
    validate_client(client_name)
    data = request.json

    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid payload format"}), 400

    from pydantic import ValidationError
    from src.dashboard.validation import ClientConfigSchema

    # 1. Load old config to preserve existing 'owned' flags
    old_config = config_mgr.load()
    old_client_config = old_config.get("clients", {}).get(client_name, {})
    old_subreddits = old_client_config.get("reddit", {}).get("subreddits", {})

    # 2. Inject existing 'owned' flags into the new data before validating
    if "reddit" in data and isinstance(data["reddit"], dict) and "subreddits" in data["reddit"] and isinstance(data["reddit"]["subreddits"], dict):
        for sub_name, sub_conf in data["reddit"]["subreddits"].items():
            if isinstance(sub_conf, dict) and sub_name in old_subreddits:
                sub_conf["owned"] = old_subreddits[sub_name].get("owned", False)

    try:
        # 3. Perform Pydantic validation
        validated_data = ClientConfigSchema.model_validate(data)
    except ValidationError as e:
        details = []
        for err in e.errors():
            details.append({
                "field": get_friendly_field_name(err["loc"]),
                "message": err["msg"]
            })
        return jsonify({
            "success": False,
            "error": "Validation failed",
            "details": details
        }), 400

    config = config_mgr.load()
    config["clients"][client_name] = validated_data.model_dump()
    config_mgr.save(config)
    return jsonify({"success": True})
