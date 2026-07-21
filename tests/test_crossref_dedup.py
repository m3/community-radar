"""Cross-reference uniqueness must be scoped per tenant.

The imported schema carried
UNIQUE (user_id, platform1, username1, platform2, username2) — no client_id.
Unlike the messages case, this one fails loudly: identity.py inserts without
ON CONFLICT, so the moment a second client produced the same match tuple the
whole sync aborted with IntegrityError (there is no per-row handling, so a
single collision takes out every match for that client).

Only one client has cross-references in production so far, which is the only
reason this has not fired yet.
"""

from sqlalchemy import UniqueConstraint

from src.db.orm import CrossReference

TENANT_SCOPED = (
    "client_id",
    "user_id",
    "platform1",
    "username1",
    "platform2",
    "username2",
)
GLOBAL = ("user_id", "platform1", "username1", "platform2", "username2")


def _unique_targets():
    return [
        tuple(col.name for col in c.columns)
        for c in CrossReference.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]


def test_orm_declares_a_tenant_scoped_unique_constraint():
    assert TENANT_SCOPED in _unique_targets()


def test_orm_does_not_declare_the_global_unique_constraint():
    assert GLOBAL not in _unique_targets(), (
        "a cross-tenant unique constraint aborts identity sync for the second client"
    )
