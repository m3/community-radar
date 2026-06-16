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
