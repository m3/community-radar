import time
import json
import traceback
import sys
from pathlib import Path

# Ensure imports work
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.db.queue import get_queue_db
from src.main import commands as CLI_COMMANDS

def run_worker():
    print("🚀 CommunityRadar Queue Worker started (Serial Mode)")
    while True:
        db = get_queue_db()
        task = db.execute(
            "SELECT * FROM tasks WHERE status = 'pending' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        
        if not task:
            db.close()
            time.sleep(5)
            continue
            
        task_id = task['id']
        print(f"Executing Task {task_id}: {task['command']} for {task['client_name'] or 'global'}...")
        
        db.execute(
            "UPDATE tasks SET status='running', started_at=datetime('now') WHERE id=?", 
            (task_id,)
        )
        db.commit()
        
        try:
            # Reconstruct args Namespace-like object
            class TaskArgs:
                def __init__(self, d, client=None):
                    self.__dict__.update(d)
                    self.client = client
            
            args_dict = json.loads(task['args_json']) if task['args_json'] else {}
            args_obj = TaskArgs(args_dict, client=task['client_name'])
            
            # Execute the actual CLI function
            func = CLI_COMMANDS[task['command']]
            func(args_obj)
            
            db.execute(
                "UPDATE tasks SET status='completed', finished_at=datetime('now') WHERE id=?", 
                (task_id,)
            )
        except Exception as e:
            err = traceback.format_exc()
            print(f"❌ Task {task_id} failed: {e}")
            db.execute(
                "UPDATE tasks SET status='failed', finished_at=datetime('now'), error_log=? WHERE id=?", 
                (err, task_id)
            )
            
        db.commit()
        db.close()
        time.sleep(2)

if __name__ == "__main__":
    run_worker()
