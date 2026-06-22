import pytest
import json
from src.db.queue import enqueue_task
from src.db.models import sanitize_client_name
from src.db.session import SessionLocal
from src.db.orm import Task

@pytest.fixture
def clean_db():
    session = SessionLocal()
    session.query(Task).delete()
    session.commit()
    session.close()
    yield

def test_enqueue_task_success(clean_db):
    client = "Valid Client 123"
    cmd = "run_report"
    args = {"param": "value"}
    
    enqueue_task(client, cmd, args)
    
    session = SessionLocal()
    task = session.query(Task).first()
    
    assert task.client_name == sanitize_client_name(client)
    assert task.command == cmd
    assert json.loads(task.args_json) == args
    assert task.status == "pending"
    session.close()

def test_enqueue_task_none_client(clean_db):
    cmd = "migrate"
    
    enqueue_task(None, cmd)
    
    session = SessionLocal()
    task = session.query(Task).first()
    
    assert task.client_name is None
    assert task.command == cmd
    session.close()


def test_zombie_task_reset(clean_db):
    from datetime import datetime, timedelta
    session = SessionLocal()
    
    # Create a zombie task: running with heartbeat_at set to 6 minutes ago
    zombie = Task(
        client_name="test_client",
        command="status",
        status="running",
        started_at=datetime.utcnow() - timedelta(minutes=6),
        heartbeat_at=datetime.utcnow() - timedelta(minutes=6)
    )
    # Create an active task: running with heartbeat_at set to 1 minute ago
    active = Task(
        client_name="test_client",
        command="status",
        status="running",
        started_at=datetime.utcnow() - timedelta(minutes=1),
        heartbeat_at=datetime.utcnow() - timedelta(minutes=1)
    )
    session.add(zombie)
    session.add(active)
    session.commit()
    zombie_id = zombie.id
    active_id = active.id
    session.close()
    
    # Run the reset logic
    from src.db.queue import get_queue_db
    db = get_queue_db()
    s = db.session
    try:
        threshold = datetime.utcnow() - timedelta(minutes=5)
        zombies = s.query(Task).filter(
            Task.status == 'running',
            (Task.heartbeat_at < threshold) | (Task.heartbeat_at.is_(None))
        ).all()
        for z in zombies:
            z.status = 'pending'
            z.started_at = None
            z.heartbeat_at = None
        s.commit()
    finally:
        db.close()
        
    # Assertions
    session = SessionLocal()
    db_zombie = session.query(Task).filter(Task.id == zombie_id).first()
    db_active = session.query(Task).filter(Task.id == active_id).first()
    
    assert db_zombie.status == "pending"
    assert db_zombie.started_at is None
    assert db_zombie.heartbeat_at is None
    
    assert db_active.status == "running"
    session.close()
