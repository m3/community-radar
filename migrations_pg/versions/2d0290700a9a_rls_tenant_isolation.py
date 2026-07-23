"""Row-level security for tenant isolation.

Enforces client_id scoping in the database rather than in the application's
SQL-rewriting layer. A non-superuser runtime role (radar_app) connects with a
per-connection GUC `app.current_client_id`; RLS policies restrict every
tenant table to rows matching it. current_setting(..., true) returns NULL when
the GUC is unset, so an unscoped connection sees nothing (fail-closed).

The role is created here WITHOUT a password (no secret in git); the deploy /
`main.py migrate` sets its password from the environment. Superusers and table
owners bypass RLS, which is exactly why the app must connect as radar_app —
see the startup check in src/db/session.py.

FORCE ROW LEVEL SECURITY is deliberately NOT set: the owner is a superuser and
bypasses RLS regardless, and FORCE would make future owner-run data migrations
subject to the (unset) GUC and touch zero rows.

Revision ID: 2d0290700a9a
Revises: 509a4c74dfbf
Create Date: 2026-07-23 09:23:45.827655

"""
from typing import Sequence, Union

from alembic import op

revision: str = '2d0290700a9a'
down_revision: Union[str, Sequence[str], None] = '509a4c74dfbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "radar_app"

TENANT_TABLES = [
    "messages", "users", "channels", "servers", "exports", "topics",
    "cross_references",
]
# Non-tenant tables the runtime role still needs access to.
GLOBAL_TABLES = ["clients", "tasks"]


def upgrade() -> None:
    # 1. Runtime role — no password here; deploy sets it from the environment.
    op.execute(
        f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOBYPASSRLS;
            END IF;
        END $$;
        """
    )

    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}"
    )
    # Future tables/sequences (created by later migrations) auto-grant.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}"
    )

    # 2. RLS policy per tenant table.
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (client_id = NULLIF(current_setting('app.current_client_id', true), '')::int)
                WITH CHECK (client_id = NULLIF(current_setting('app.current_client_id', true), '')::int)
            """
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    # Role and grants are left in place; dropping a role that may own nothing
    # is safe to skip and avoids failures if objects still reference it.
