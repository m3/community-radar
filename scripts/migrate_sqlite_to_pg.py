import sqlite3
import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from src.db.orm import Client, Server, Channel, User, Message, Export, CrossReference, Topic, Task
from src.db.session import DATABASE_URL, SessionLocal

DATA_DIR = Path(__file__).parent.parent / "data"
CLIENTS_DIR = DATA_DIR / "clients"
QUEUE_DB_PATH = DATA_DIR / "queue.db"

def parse_date(date_str):
    if not date_str:
        return None
    if isinstance(date_str, datetime):
        return date_str
    try:
        # Try ISO format
        return datetime.fromisoformat(date_str)
    except ValueError:
        try:
            # Try sqlite datetime('now') format
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

def migrate_queue():
    if not QUEUE_DB_PATH.exists():
        return
        
    print("Migrating execution queue...")
    sqlite_conn = sqlite3.connect(QUEUE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_session = SessionLocal()
    
    try:
        # Cleanup
        pg_session.query(Task).delete()
        pg_session.commit()
        
        rows = sqlite_conn.execute("SELECT * FROM tasks").fetchall()
        for row in rows:
            task = Task(
                client_name=row["client_name"],
                command=row["command"],
                args_json=row["args_json"],
                status=row["status"],
                error_log=row["error_log"],
                created_at=parse_date(row["created_at"]),
                started_at=parse_date(row["started_at"]),
                finished_at=parse_date(row["finished_at"])
            )
            pg_session.add(task)
        pg_session.commit()
        print("Finished migrating queue")
    except Exception as e:
        pg_session.rollback()
        print(f"Error migrating queue: {e}")
    finally:
        pg_session.close()
        sqlite_conn.close()

def migrate_client(client_db_path: Path):
    client_name = client_db_path.stem
    print(f"Migrating client: {client_name}")
    
    # Connect to SQLite
    sqlite_conn = sqlite3.connect(client_db_path)
    sqlite_conn.row_factory = sqlite3.Row
    
    # Connect to PG
    pg_session = SessionLocal()
    
    try:
        # 1. Create or get Client
        client = pg_session.query(Client).filter_by(name=client_name).first()
        if not client:
            client = Client(name=client_name)
            pg_session.add(client)
            pg_session.commit()
            pg_session.refresh(client)
        
        client_id = client.id
        
        # 0. Cleanup existing data for this client in PG
        print(f"  Cleaning up existing data for {client_name} (ID: {client_id})")
        pg_session.query(Topic).filter_by(client_id=client_id).delete()
        pg_session.query(CrossReference).filter_by(client_id=client_id).delete()
        pg_session.query(Export).filter_by(client_id=client_id).delete()
        pg_session.query(Message).filter_by(client_id=client_id).delete()
        pg_session.query(Channel).filter_by(client_id=client_id).delete()
        pg_session.query(User).filter_by(client_id=client_id).delete()
        pg_session.query(Server).filter_by(client_id=client_id).delete()
        pg_session.commit()
        
        # 2. Migrate Servers
        rows = sqlite_conn.execute("SELECT * FROM servers").fetchall()
        server_ids = set()
        for row in rows:
            server = Server(
                id=row["id"],
                client_id=client_id,
                name=row["name"],
                data_source=row["data_source"],
                first_scan=parse_date(row["first_scan"]),
                last_scan=parse_date(row["last_scan"]),
                total_messages=row["total_messages"],
                total_users=row["total_users"],
                created_at=parse_date(row["created_at"]),
                updated_at=parse_date(row["updated_at"])
            )
            pg_session.merge(server)
            server_ids.add(row["id"])
        pg_session.commit()
        
        # 3. Migrate Channels
        rows = sqlite_conn.execute("SELECT * FROM channels").fetchall()
        channel_ids = set()
        for row in rows:
            channel = Channel(
                id=row["id"],
                client_id=client_id,
                server_id=row["server_id"],
                name=row["name"],
                topic=row["topic"],
                first_scan=parse_date(row["first_scan"]),
                last_scan=parse_date(row["last_scan"]),
                last_message_ts=parse_date(row["last_message_ts"]),
                message_count=row["message_count"],
                status=row["status"],
                created_at=parse_date(row["created_at"]),
                updated_at=parse_date(row["updated_at"])
            )
            pg_session.merge(channel)
            channel_ids.add(row["id"])
        pg_session.commit()
            
        # 4. Migrate Users
        rows = sqlite_conn.execute("SELECT * FROM users").fetchall()
        user_ids = set()
        for row in rows:
            user = User(
                id=row["id"],
                client_id=client_id,
                display_name=row["display_name"],
                username=row["username"],
                role=row["role"],
                messages=row["messages"],
                reactions_given=row["reactions_given"],
                reactions_received=row["reactions_received"],
                first_seen=parse_date(row["first_seen"]),
                last_seen=parse_date(row["last_seen"]),
                sentiment=row["sentiment"],
                notes=row["notes"],
                created_at=parse_date(row["created_at"]),
                updated_at=parse_date(row["updated_at"])
            )
            pg_session.merge(user)
            user_ids.add(row["id"])
        pg_session.commit()
            
        # Pre-check for missing Foreign Keys in Messages
        msg_rows = sqlite_conn.execute("SELECT DISTINCT channel_id, user_id FROM messages").fetchall()
        for row in msg_rows:
            c_id = row["channel_id"]
            u_id = row["user_id"]
            
            if c_id and c_id not in channel_ids:
                print(f"  Creating stub channel {c_id}")
                stub_server_id = "stub_server"
                if stub_server_id not in server_ids:
                    pg_session.merge(Server(id=stub_server_id, client_id=client_id, name="Stub Server"))
                    server_ids.add(stub_server_id)
                
                pg_session.merge(Channel(id=c_id, client_id=client_id, server_id=stub_server_id, name=f"Stub Channel {c_id}"))
                channel_ids.add(c_id)
            
            if u_id and u_id not in user_ids:
                print(f"  Creating stub user {u_id}")
                pg_session.merge(User(id=u_id, client_id=client_id, username=f"stub_user_{u_id}"))
                user_ids.add(u_id)
        pg_session.commit()

        # 5. Migrate Messages (Batch)
        rows = sqlite_conn.execute("SELECT * FROM messages").fetchall()
        for i in range(0, len(rows), 1000):
            batch = rows[i:i+1000]
            for row in batch:
                msg = Message(
                    client_id=client_id,
                    message_id=row["message_id"],
                    channel_id=row["channel_id"],
                    user_id=row["user_id"],
                    content=row["content"],
                    timestamp=parse_date(row["timestamp"]),
                    reply_to=row["reply_to"],
                    reactions=row["reactions"],
                    export_batch=row["export_batch"],
                    platform=row["platform"],
                    created_at=parse_date(row["created_at"])
                )
                pg_session.add(msg)
            pg_session.commit()
            
        # 6. Migrate Exports
        rows = sqlite_conn.execute("SELECT * FROM exports").fetchall()
        for row in rows:
            export = Export(
                client_id=client_id,
                server_id=row["server_id"],
                channel_id=row["channel_id"],
                export_ts=parse_date(row["export_ts"]),
                messages=row["messages"],
                new_users=row["new_users"],
                duration_s=row["duration_s"],
                status=row["status"],
                notes=row["notes"],
                created_at=parse_date(row["created_at"])
            )
            pg_session.add(export)
            
        # 7. Migrate Cross References
        rows = sqlite_conn.execute("SELECT * FROM cross_references").fetchall()
        for row in rows:
            xref = CrossReference(
                client_id=client_id,
                user_id=row["user_id"],
                platform1=row["platform1"],
                username1=row["username1"],
                platform2=row["platform2"],
                username2=row["username2"],
                match_type=row["match_type"],
                confidence=row["confidence"],
                created_at=parse_date(row["created_at"])
            )
            pg_session.add(xref)
            
        # 8. Migrate Topics
        rows = sqlite_conn.execute("SELECT * FROM topics").fetchall()
        for row in rows:
            topic = Topic(
                client_id=client_id,
                name=row["name"],
                category=row["category"],
                mention_count=row["mention_count"],
                first_seen=parse_date(row["first_seen"]),
                last_seen=parse_date(row["last_seen"]),
                created_at=parse_date(row["created_at"])
            )
            pg_session.add(topic)
            
        pg_session.commit()
        print(f"Finished migrating {client_name}")
        
    except Exception as e:
        pg_session.rollback()
        print(f"Error migrating {client_name}: {e}")
    finally:
        pg_session.close()
        sqlite_conn.close()

def main():
    migrate_queue()
    if CLIENTS_DIR.exists():
        db_files = list(CLIENTS_DIR.glob("*.db"))
        for db_file in db_files:
            migrate_client(db_file)
    else:
        print("No clients directory found.")

if __name__ == "__main__":
    main()
