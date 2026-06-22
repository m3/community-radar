import time
import json
import traceback
import sys
from pathlib import Path
from datetime import datetime, timedelta
import threading
from sqlalchemy.exc import DBAPIError

# Ensure imports work
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.db.queue import get_queue_db
from src.main import commands as CLI_COMMANDS
from src.db.orm import Task

class HeartbeatThread(threading.Thread):
    def __init__(self, task_id, interval=30):
        super().__init__()
        self.task_id = task_id
        self.interval = interval
        self.stop_event = threading.Event()
        
    def run(self):
        while not self.stop_event.wait(self.interval):
            db = get_queue_db()
            try:
                db.execute(
                    "UPDATE tasks SET heartbeat_at = ? WHERE id = ?",
                    (datetime.utcnow(), self.task_id)
                )
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()
                
    def stop(self):
        self.stop_event.set()

def run_worker():
    print("🚀 CommunityRadar Queue Worker started (Concurrent Mode)")
    while True:
        db = get_queue_db()
        session = db.session
        
        # 1. Reset zombie tasks (running for > 5 minutes without heartbeat)
        try:
            threshold = datetime.utcnow() - timedelta(minutes=5)
            zombies = session.query(Task).filter(
                Task.status == 'running',
                (Task.heartbeat_at < threshold) | (Task.heartbeat_at.is_(None))
            ).all()
            for z in zombies:
                z.status = 'pending'
                z.started_at = None
                z.heartbeat_at = None
            session.commit()
        except DBAPIError:
            session.rollback()
            
        # 2. Select next pending task
        task = None
        try:
            task = session.query(Task).filter(Task.status == 'pending').order_by(Task.id.asc()).first()
        except DBAPIError:
            session.rollback()
            
        if not task:
            session.close()
            time.sleep(5)
            continue
            
        task_id = task.id
        command = task.command
        client_name = task.client_name
        args_json = task.args_json
        
        # 3. Atomic claim check
        claimed = False
        try:
            cursor = db.execute(
                "UPDATE tasks SET status='running', started_at=?, heartbeat_at=? WHERE id=? AND status='pending'", 
                (datetime.utcnow(), datetime.utcnow(), task_id)
            )
            db.commit()
            if cursor.rowcount > 0:
                claimed = True
        except (DBAPIError, Exception):
            db.rollback()
            
        if not claimed:
            # Failed to claim (another worker got it or DB lock raised)
            db.close()
            time.sleep(1)
            continue
            
        print(f"Executing Task {task_id}: {command} for {client_name or 'global'}...")
        
        # 4. Start heartbeat thread
        hb_thread = HeartbeatThread(task_id)
        hb_thread.daemon = True
        hb_thread.start()
        
        try:
            # Reconstruct args Namespace-like object
            class TaskArgs:
                def __init__(self, d, client=None):
                    self.__dict__.update(d)
                    self.client = client
            
            args_dict = json.loads(args_json) if args_json else {}
            args_obj = TaskArgs(args_dict, client=client_name)
            
            # Execute the actual CLI function
            func = CLI_COMMANDS[command]
            func(args_obj)
            
            # Mark completed
            db.execute(
                "UPDATE tasks SET status='completed', finished_at=? WHERE id=?", 
                (datetime.utcnow(), task_id)
            )
            db.commit()
        except Exception as e:
            err = traceback.format_exc()
            print(f"❌ Task {task_id} failed: {e}")
            try:
                db.execute(
                    "UPDATE tasks SET status='failed', finished_at=?, error_log=? WHERE id=?", 
                    (datetime.utcnow(), err, task_id)
                )
                db.commit()
            except Exception:
                db.rollback()
        finally:
            hb_thread.stop()
            hb_thread.join(timeout=5)
            db.close()
            
        time.sleep(2)

if __name__ == "__main__":
    run_worker()
