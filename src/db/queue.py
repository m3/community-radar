import json
from datetime import datetime
from src.db.models import sanitize_client_name, get_db
from src.db.orm import Task
from src.db.session import SessionLocal

def get_queue_db():
    """
    Returns a LegacySessionWrapper for the global context (client_id=0)
    to maintain compatibility with queue management code.
    """
    return get_db(None)

def enqueue_task(client_name, command, args_dict=None):
    clean_name = sanitize_client_name(client_name) if client_name else None
    args_json = json.dumps(args_dict) if args_dict else None
    
    session = SessionLocal()
    try:
        task = Task(
            client_name=clean_name,
            command=command,
            args_json=args_json,
            status='pending'
        )
        session.add(task)
        session.commit()
    finally:
        session.close()
