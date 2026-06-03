"""add users table and link contacts to users

Revision ID: a1b2c3d4e5f6
Revises: f60ca8e17744
Create Date: 2026-05-21 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f60ca8e17744"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users table.
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("avatar", sa.String(length=255), nullable=True),
        sa.Column(
            "confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # 2. Existing global unique constraints on contacts must go — uniqueness
    #    becomes per-user (so two users can both have "tony@stark.io").
    op.drop_constraint("contacts_email_key", "contacts", type_="unique")
    op.drop_constraint("contacts_phone_key", "contacts", type_="unique")

    # 3. Attach contacts to users.
    op.add_column(
        "contacts",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_contacts_user_id", "contacts", ["user_id"], unique=False
    )
    op.create_foreign_key(
        "fk_contacts_user_id_users",
        "contacts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 4. Backfill: if there are any orphan contacts left from homework_8,
    #    create a service user and assign them all to it so the column can
    #    be made NOT NULL safely.
    op.execute(
        """
        DO $$
        DECLARE
            orphan_count integer;
            service_user_id integer;
        BEGIN
            SELECT COUNT(*) INTO orphan_count FROM contacts WHERE user_id IS NULL;
            IF orphan_count > 0 THEN
                INSERT INTO users (
                    username, email, hashed_password, confirmed
                ) VALUES (
                    'legacy_owner',
                    'legacy@local.invalid',
                    '!disabled',
                    true
                )
                RETURNING id INTO service_user_id;
                UPDATE contacts SET user_id = service_user_id WHERE user_id IS NULL;
            END IF;
        END$$;
        """
    )

    op.alter_column("contacts", "user_id", nullable=False)

    # 5. Per-user uniqueness on email and phone.
    op.create_unique_constraint(
        "uq_contacts_email_user", "contacts", ["email", "user_id"]
    )
    op.create_unique_constraint(
        "uq_contacts_phone_user", "contacts", ["phone", "user_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_contacts_phone_user", "contacts", type_="unique")
    op.drop_constraint("uq_contacts_email_user", "contacts", type_="unique")
    op.drop_constraint("fk_contacts_user_id_users", "contacts", type_="foreignkey")
    op.drop_index("ix_contacts_user_id", table_name="contacts")
    op.drop_column("contacts", "user_id")
    op.create_unique_constraint("contacts_phone_key", "contacts", ["phone"])
    op.create_unique_constraint("contacts_email_key", "contacts", ["email"])
    op.drop_table("users")
