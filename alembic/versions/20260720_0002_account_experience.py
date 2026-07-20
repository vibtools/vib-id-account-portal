"""Add account experience profile media and social links.

Revision ID: 20260720_0002
Revises: 20260630_0001
Create Date: 2026-07-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260720_0002"
down_revision = "20260630_0001"
branch_labels = None
depends_on = None


def _uuid_type() -> sa.types.TypeEngine[object]:
    bind = op.get_context().bind
    if bind is not None and bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    uuid_type = _uuid_type()
    op.create_table(
        "user_social_links",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("normalized_url", sa.String(length=500), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="apps"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("platform = lower(platform)", name="ck_social_platform_lowercase"),
        sa.CheckConstraint("visibility IN ('apps', 'private')", name="ck_social_visibility"),
        sa.UniqueConstraint("subject", "platform", name="uq_social_link_subject_platform"),
    )
    op.create_index("ix_user_social_links_subject", "user_social_links", ["subject"])

    op.create_table(
        "user_profile_photos",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("avatar_key", sa.String(length=96), nullable=False),
        sa.Column("mime_type", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("image_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes > 0", name="ck_profile_photo_size_positive"),
        sa.CheckConstraint(
            "mime_type IN ('image/png', 'image/jpeg', 'image/webp')",
            name="ck_profile_photo_mime",
        ),
        sa.UniqueConstraint("subject", name="uq_user_profile_photos_subject"),
        sa.UniqueConstraint("avatar_key", name="uq_user_profile_photos_avatar_key"),
    )
    op.create_index("ix_user_profile_photos_subject", "user_profile_photos", ["subject"])
    op.create_index("ix_user_profile_photos_avatar_key", "user_profile_photos", ["avatar_key"])
    op.create_index("ix_user_profile_photos_sha256_hash", "user_profile_photos", ["sha256_hash"])


def downgrade() -> None:
    op.drop_index("ix_user_profile_photos_sha256_hash", table_name="user_profile_photos")
    op.drop_index("ix_user_profile_photos_avatar_key", table_name="user_profile_photos")
    op.drop_index("ix_user_profile_photos_subject", table_name="user_profile_photos")
    op.drop_table("user_profile_photos")
    op.drop_index("ix_user_social_links_subject", table_name="user_social_links")
    op.drop_table("user_social_links")
