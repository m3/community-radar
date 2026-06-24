import sqlite3, re, sys, psycopg2

SQLITE_PATH = '/tmp/pure-pool-pro.db'

conn = sqlite3.connect(SQLITE_PATH)
conn.row_factory = sqlite3.Row

def rows_to_dicts(rows):
    return [dict(r) for r in rows]

servers = rows_to_dicts(conn.execute('SELECT * FROM servers').fetchall())
channels = rows_to_dicts(conn.execute('SELECT * FROM channels').fetchall())
users = rows_to_dicts(conn.execute('SELECT * FROM users').fetchall())
messages = rows_to_dicts(conn.execute('SELECT * FROM messages').fetchall())
topics = rows_to_dicts(conn.execute('SELECT * FROM topics').fetchall())
cross_refs = rows_to_dicts(conn.execute('SELECT * FROM cross_references').fetchall())
exports = rows_to_dicts(conn.execute('SELECT * FROM exports').fetchall())
conn.close()

print(f"SQLite: {len(servers)} servers, {len(channels)} channels, {len(users)} users, {len(messages)} messages, {len(exports)} exports, {len(topics)} topics, {len(cross_refs)} cross-refs")

pg = psycopg2.connect(dbname='community_radar', user='community_radar', host='/var/run/postgresql')
pg.autocommit = False
cur = pg.cursor()

# Truncate all data first (clean slate)
cur.execute('TRUNCATE messages, channels, users, servers, topics, cross_references, exports, alembic_version RESTART IDENTITY CASCADE')
pg.commit()

# Use pure-pool-pro as the single client
cur.execute('INSERT INTO clients (name, created_at, updated_at) VALUES (%s, NOW(), NOW()) ON CONFLICT (name) DO UPDATE SET updated_at = NOW() RETURNING id', ('pure-pool-pro',))
client_id = cur.fetchone()[0]
pg.commit()

print(f"Client: pure-pool-pro (id={client_id})")

# 1. Insert servers
created = 0
for s in servers:
    cur.execute('''INSERT INTO servers (id, client_id, name, data_source, first_scan, last_scan,
                   total_messages, total_users, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING''',
                (s['id'], client_id, s['name'], s.get('data_source','discord'),
                 s['first_scan'], s['last_scan'], s['total_messages'], s['total_users'],
                 s['created_at'], s['updated_at']))
    if cur.rowcount: created += 1
pg.commit()
print(f"Servers: {created}")

# 2. Insert channels
created = 0
for c in channels:
    cur.execute('''INSERT INTO channels (id, client_id, server_id, name, topic,
                   first_scan, last_scan, last_message_ts, message_count, status, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING''',
                (c['id'], client_id, c['server_id'], c['name'], c.get('topic'),
                 c['first_scan'], c['last_scan'], c['last_message_ts'],
                 c['message_count'], c.get('status','active'), c['created_at'], c['updated_at']))
    created += 1
pg.commit()
print(f"Channels: {created}")

# 3. Insert users
created = 0
for u in users:
    cur.execute('''INSERT INTO users (id, client_id, display_name, username, role,
                   messages, reactions_given, reactions_received, first_seen, last_seen,
                   sentiment, notes, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING''',
                (u['id'], client_id, u.get('display_name'), u.get('username'),
                 u.get('role','member'), u.get('messages',0), u.get('reactions_given',0),
                 u.get('reactions_received',0), u.get('first_seen'), u.get('last_seen'),
                 u.get('sentiment'), u.get('notes'), u.get('created_at'), u.get('updated_at')))
    created += 1
pg.commit()
print(f"Users: {created}")

# 4. Insert topics
created = 0
for t in topics:
    cur.execute('''INSERT INTO topics (id, client_id, name, category, mention_count,
                   first_seen, last_seen, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING''',
                (t['id'], client_id, t['name'], t.get('category'), t.get('mention_count',0),
                 t.get('first_seen'), t.get('last_seen'), t.get('created_at')))
    created += 1
pg.commit()
print(f"Topics: {created}")

# 5. Insert cross_references
created = 0
for xr in cross_refs:
    cur.execute('''INSERT INTO cross_references (id, client_id, user_id, platform1,
                   username1, platform2, username2, match_type, confidence, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING''',
                (xr['id'], client_id, xr.get('user_id'), xr.get('platform1'),
                 xr.get('username1'), xr.get('platform2'), xr.get('username2'),
                 xr.get('match_type'), xr.get('confidence',0), xr.get('created_at')))
    created += 1
pg.commit()
print(f"Cross-refs: {created}")

# 6. Insert exports
created = 0
for e in exports:
    cur.execute('''INSERT INTO exports (id, client_id, server_id, channel_id, export_ts,
                   messages, new_users, duration_s, status, notes, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING''',
                (e['id'], client_id, e.get('server_id'), e.get('channel_id'),
                 e.get('export_ts'), e.get('messages',0), e.get('new_users',0),
                 e.get('duration_s',0), e.get('status'), e.get('notes'), e.get('created_at')))
    created += 1
pg.commit()
print(f"Exports: {created}")

# 7. Insert messages (batched, let PG assign IDs)
created = 0
batch = []
for m in messages:
    batch.append((client_id, m.get('message_id'), m.get('channel_id'),
                  m.get('user_id'), m.get('content'), m.get('timestamp'),
                  m.get('reply_to'), m.get('reactions',0), m.get('export_batch'),
                  m.get('platform','discord'), m.get('created_at')))
    if len(batch) >= 5000:
        cur.executemany('''INSERT INTO messages (client_id, message_id, channel_id, user_id,
                          content, timestamp, reply_to, reactions, export_batch, platform, created_at)
                          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                          ON CONFLICT (message_id) DO NOTHING''', batch)
        created += len(batch); batch = []
        pg.commit()
if batch:
    cur.executemany('''INSERT INTO messages (client_id, message_id, channel_id, user_id,
                      content, timestamp, reply_to, reactions, export_batch, platform, created_at)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                      ON CONFLICT (message_id) DO NOTHING''', batch)
    created += len(batch)
pg.commit()
print(f"Messages: {created}")

pg.commit()
cur.close()
pg.close()
print("Migration complete!")
