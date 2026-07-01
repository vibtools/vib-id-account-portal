"""Create Vib ID production schema.

Revision ID: 20260630_0001
Revises:
Create Date: 2026-06-30 00:00:00+00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260630_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.Column("phone_country_code", sa.String(length=8), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("preferred_language", sa.String(length=16), nullable=False),
        sa.Column("organization_name", sa.String(length=160), nullable=True),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("avatar_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(subject) >= 3", name="ck_user_profiles_subject_length"),
        sa.CheckConstraint("country_code IS NULL OR length(country_code) = 2", name="ck_country_code"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject"),
    )
    op.create_index("ix_user_profiles_subject", "user_profiles", ["subject"], unique=True)

    op.create_table(
        "user_contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("contact_type", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject", "contact_type", "normalized_value", name="uq_contact_subject_type_value"),
    )
    op.create_index("ix_user_contacts_subject", "user_contacts", ["subject"], unique=False)
    op.create_index(
        "uq_contact_primary_per_type",
        "user_contacts",
        ["subject", "contact_type"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    op.create_table(
        "user_preferences",
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("theme", sa.String(length=16), server_default="system", nullable=False),
        sa.Column("locale", sa.String(length=16), server_default="en", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("security_email_notifications", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("product_announcements", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("subject"),
    )

    op.create_table(
        "portal_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_hash", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("encrypted_token_bundle", sa.LargeBinary(), nullable=False),
        sa.Column("user_agent_summary", sa.String(length=255), nullable=False),
        sa.Column("ip_privacy_value", sa.String(length=64), nullable=False),
        sa.Column("device_label", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=80), nullable=True),
        sa.Column("oidc_sid", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_hash"),
    )
    op.create_index("ix_portal_sessions_session_hash", "portal_sessions", ["session_hash"], unique=True)
    op.create_index("ix_portal_sessions_subject", "portal_sessions", ["subject"], unique=False)
    op.create_index("ix_portal_sessions_last_seen_at", "portal_sessions", ["last_seen_at"], unique=False)
    op.create_index("ix_portal_sessions_revoked_at", "portal_sessions", ["revoked_at"], unique=False)
    op.create_index("ix_portal_sessions_oidc_sid", "portal_sessions", ["oidc_sid"], unique=False)
    op.create_index(
        "ix_portal_sessions_subject_active",
        "portal_sessions",
        ["subject", "revoked_at", "absolute_expires_at"],
        unique=False,
    )

    op.create_table(
        "oidc_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("encrypted_code_verifier", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_oidc_transactions_state_hash", "oidc_transactions", ["state_hash"], unique=True)
    op.create_index("ix_oidc_transactions_expires_at", "oidc_transactions", ["expires_at"], unique=False)

    op.create_table(
        "logout_token_replays",
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("jti_hash"),
    )
    op.create_index("ix_logout_token_replays_expires_at", "logout_token_replays", ["expires_at"], unique=False)

    op.create_table(
        "security_activity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_severity", sa.String(length=16), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("request_correlation_id", sa.String(length=64), nullable=False),
        sa.Column("ip_privacy_value", sa.String(length=64), nullable=False),
        sa.Column("user_agent_summary", sa.String(length=255), nullable=False),
        sa.Column("event_metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_activity_subject", "security_activity", ["subject"], unique=False)
    op.create_index("ix_security_activity_event_type", "security_activity", ["event_type"], unique=False)
    op.create_index("ix_security_activity_request_correlation_id", "security_activity", ["request_correlation_id"], unique=False)
    op.create_index("ix_security_activity_occurred_at", "security_activity", ["occurred_at"], unique=False)
    op.create_index("ix_security_activity_subject_occurred", "security_activity", ["subject", "occurred_at"], unique=False)

    op.create_table(
        "rate_limit_buckets",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key_hash"),
    )
    op.create_index("ix_rate_limit_buckets_expires_at", "rate_limit_buckets", ["expires_at"], unique=False)

    op.create_table(
        "service_registry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("description", sa.String(length=280), nullable=False),
        sa.Column("icon_reference", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="100", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("service_key = lower(service_key)", name="ck_service_key_lowercase"),
        sa.CheckConstraint("sort_order >= 0", name="ck_service_sort_order"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain"),
        sa.UniqueConstraint("service_key"),
    )
    op.create_index("ix_service_registry_service_key", "service_registry", ["service_key"], unique=True)

    op.create_table(
        "user_service_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("first_connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_status", sa.String(length=16), nullable=False),
        sa.Column("connection_metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["service_registry.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject", "service_id", name="uq_user_service_connection"),
    )
    op.create_index("ix_user_service_connections_subject", "user_service_connections", ["subject"], unique=False)
    op.create_index("ix_user_service_connections_service_id", "user_service_connections", ["service_id"], unique=False)
    op.create_index("ix_user_service_connections_last_authenticated_at", "user_service_connections", ["last_authenticated_at"], unique=False)

    op.create_table(
        "migration_locks",
        sa.Column("lock_id", sa.BigInteger(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("lock_id"),
    )


def downgrade() -> None:
    op.drop_table("migration_locks")
    op.drop_index("ix_user_service_connections_last_authenticated_at", table_name="user_service_connections")
    op.drop_index("ix_user_service_connections_service_id", table_name="user_service_connections")
    op.drop_index("ix_user_service_connections_subject", table_name="user_service_connections")
    op.drop_table("user_service_connections")
    op.drop_index("ix_service_registry_service_key", table_name="service_registry")
    op.drop_table("service_registry")
    op.drop_index("ix_rate_limit_buckets_expires_at", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
    op.drop_index("ix_security_activity_subject_occurred", table_name="security_activity")
    op.drop_index("ix_security_activity_occurred_at", table_name="security_activity")
    op.drop_index("ix_security_activity_request_correlation_id", table_name="security_activity")
    op.drop_index("ix_security_activity_event_type", table_name="security_activity")
    op.drop_index("ix_security_activity_subject", table_name="security_activity")
    op.drop_table("security_activity")
    op.drop_index("ix_logout_token_replays_expires_at", table_name="logout_token_replays")
    op.drop_table("logout_token_replays")
    op.drop_index("ix_oidc_transactions_expires_at", table_name="oidc_transactions")
    op.drop_index("ix_oidc_transactions_state_hash", table_name="oidc_transactions")
    op.drop_table("oidc_transactions")
    op.drop_index("ix_portal_sessions_subject_active", table_name="portal_sessions")
    op.drop_index("ix_portal_sessions_oidc_sid", table_name="portal_sessions")
    op.drop_index("ix_portal_sessions_revoked_at", table_name="portal_sessions")
    op.drop_index("ix_portal_sessions_last_seen_at", table_name="portal_sessions")
    op.drop_index("ix_portal_sessions_subject", table_name="portal_sessions")
    op.drop_index("ix_portal_sessions_session_hash", table_name="portal_sessions")
    op.drop_table("portal_sessions")
    op.drop_table("user_preferences")
    op.drop_index("uq_contact_primary_per_type", table_name="user_contacts")
    op.drop_index("ix_user_contacts_subject", table_name="user_contacts")
    op.drop_table("user_contacts")
    op.drop_index("ix_user_profiles_subject", table_name="user_profiles")
    op.drop_table("user_profiles")
