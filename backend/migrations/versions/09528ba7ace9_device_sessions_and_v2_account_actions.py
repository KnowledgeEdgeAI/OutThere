"""device sessions and v2 account actions

Revision ID: 09528ba7ace9
Revises: f6b4936e2c81
"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "09528ba7ace9"
down_revision = "f6b4936e2c81"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "actionreceipt",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("user_id", "action_id"),
    )
    op.create_index(
        op.f("ix_actionreceipt_expires_at"), "actionreceipt", ["expires_at"], unique=False
    )
    op.create_table(
        "device",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "installation_id"),
    )
    op.create_index(op.f("ix_device_user_id"), "device", ["user_id"], unique=False)
    op.create_table(
        "authoperation",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("renewal_id", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("encrypted_result", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["authsession.id"],
        ),
        sa.PrimaryKeyConstraint("session_id", "renewal_id"),
    )
    op.create_index(
        op.f("ix_authoperation_expires_at"), "authoperation", ["expires_at"], unique=False
    )
    with op.batch_alter_table("authsession") as batch:
        batch.add_column(sa.Column("device_id", sa.Uuid(), nullable=True))
        batch.create_index("ix_authsession_device_id", ["device_id"])
        batch.create_foreign_key("fk_authsession_device", "device", ["device_id"], ["id"])
    op.add_column("user", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("user", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_user_phone", "user", ["phone"], unique=True)


def downgrade():
    op.drop_index("ix_user_phone", table_name="user")
    op.drop_column("user", "version")
    op.drop_column("user", "phone")
    op.drop_table("authoperation")
    with op.batch_alter_table("authsession") as batch:
        batch.drop_constraint("fk_authsession_device", type_="foreignkey")
        batch.drop_index("ix_authsession_device_id")
        batch.drop_column("device_id")
    op.drop_table("device")
    op.drop_table("actionreceipt")
