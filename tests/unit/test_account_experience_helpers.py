from __future__ import annotations

from typing import ClassVar

import pytest

from app.account_experience.profile_media import AvatarValidationError, detect_mime_type
from app.account_experience.service import avatar_url_for_key, portable_profile_for_subject
from app.account_security.service import (
    _central_client_ids,
    _client_candidates,
    _millis_to_datetime,
    application_summaries,
    claims_from_auth,
    safe_central_sessions,
)
from app.services_registry.repository import ensure_default_service


def test_avatar_detection_supports_jpeg_and_webp_and_mismatch() -> None:
    assert detect_mime_type(b"\xff\xd8\xffjpeg") == "image/jpeg"
    assert detect_mime_type(b"RIFFxxxxWEBPpayload") == "image/webp"
    with pytest.raises(AvatarValidationError):
        detect_mime_type(b"GIF89a")


def test_avatar_url_and_claim_helpers() -> None:
    assert (
        avatar_url_for_key("https://id.vib.tools/", "abc.png")
        == "https://id.vib.tools/media/profile-avatars/abc.png"
    )
    assert avatar_url_for_key("https://id.vib.tools", None) is None

    class Auth:
        token_bundle: ClassVar[dict[str, str]] = {"_id_claims": "not-a-dict"}

    assert claims_from_auth(Auth()) == {}


@pytest.mark.asyncio
async def test_portable_profile_absent_subject_and_safe_central_fallbacks(client) -> None:
    async with client.app.state.database.session_factory() as db:
        profile = await portable_profile_for_subject(
            db, subject="missing-subject", app_base_url="http://testserver"
        )
        assert profile.subject == "missing-subject"
        assert profile.avatar_url is None
    assert await safe_central_sessions(object(), "subject") == []

    class BadKeycloak:
        async def list_user_sessions(self, subject: str) -> str:
            return "bad"

    assert await safe_central_sessions(BadKeycloak(), "subject") == []


def test_central_client_helpers_cover_unknowns_and_seconds() -> None:
    assert _client_candidates("", None) == []
    assert "ygit" in _client_candidates("ygit-net")
    assert _central_client_ids([{"clients": ["ygit-dev"], "lastAccess": 1000}]) == [
        ("ygit-dev", 1000)
    ]
    assert _millis_to_datetime(None) is None
    assert _millis_to_datetime(1000).year == 1970


def test_default_service_seed_and_duplicate_summary_skip(client, login_user) -> None:
    login = login_user(subject="default-service-user")

    async def run() -> list[str]:
        async with client.app.state.database.session_factory() as db:
            service = await ensure_default_service(db, service_key="ygit")
            assert service is not None
            apps = await application_summaries(
                db,
                login.subject,
                central_sessions=[
                    {
                        "clients": {"vib-id-portal": "Vib ID", "unknown": "Unknown"},
                        "lastAccess": 1000,
                    },
                    {"clients": {"ygit": "YGIT"}, "lastAccess": None},
                ],
            )
            return [item.service_key for item in apps]

    import asyncio

    assert asyncio.run(run()) == ["ygit"]


def test_route_functions_direct_success_paths(client, login_user) -> None:
    login = login_user(subject="direct-route-user")

    class RequestStub:
        app = client.app

    async def run() -> tuple[dict[str, object], int]:
        from app.account_experience.routes import (
            current_portable_profile,
            internal_portable_profile,
        )

        async with client.app.state.database.session_factory() as db:
            auth = await client.app.state.session_service.resolve(db, login.raw_session_id)
            assert auth is not None
            current = await current_portable_profile(RequestStub(), db, auth)
            internal = await internal_portable_profile(
                login.subject,
                RequestStub(),
                "Bearer valid-service-token",
                db,
            )
            return current, internal.status_code

    import asyncio

    current_payload, internal_status = asyncio.run(run())
    assert current_payload["subject"] == login.subject
    assert internal_status == 200


def test_profile_avatar_media_direct_not_found_paths(monkeypatch) -> None:
    from fastapi import HTTPException

    from app.account_experience import routes

    class DummyDB:
        pass

    async def fake_get_photo(db, *, avatar_key: str):
        return None

    async def run() -> tuple[int, int]:
        monkeypatch.setattr(routes, "get_profile_photo_by_key", fake_get_photo)
        with pytest.raises(HTTPException) as bad_key:
            await routes.profile_avatar_media("bad..key", DummyDB())
        with pytest.raises(HTTPException) as missing:
            await routes.profile_avatar_media("missing.png", DummyDB())
        return bad_key.value.status_code, missing.value.status_code

    import asyncio

    assert asyncio.run(run()) == (404, 404)


def test_account_experience_repository_direct_paths(client) -> None:
    import asyncio

    from app.accounts.repository import (
        delete_profile_photo,
        delete_social_link,
        get_profile_photo,
        get_profile_photo_by_key,
        upsert_profile_photo,
        upsert_social_link,
    )
    from app.accounts.schemas import SocialLinkPayload

    async def run() -> tuple[bool, bool, bool, str | None]:
        async with client.app.state.database.session_factory() as db:
            subject = "repo-direct-user"
            link = await upsert_social_link(
                db,
                subject=subject,
                payload=SocialLinkPayload(
                    platform="website",
                    label="Website",
                    url="https://vib.tools",
                    visibility="apps",
                ),
            )
            await upsert_social_link(
                db,
                subject=subject,
                payload=SocialLinkPayload(
                    platform="website",
                    label="Main Website",
                    url="https://vib.tools/docs",
                    visibility="private",
                ),
            )
            photo = await upsert_profile_photo(
                db,
                subject=subject,
                avatar_key="direct-avatar.png",
                mime_type="image/png",
                size_bytes=16,
                sha256_hash="abc123",
                image_bytes=b"\x89PNG\r\n\x1a\nimage",
            )
            by_subject = await get_profile_photo(db, subject=subject)
            by_key = await get_profile_photo_by_key(db, avatar_key=photo.avatar_key)
            link_deleted = await delete_social_link(db, subject=subject, link_id=link.id)
            photo_deleted = await delete_profile_photo(db, subject=subject)
            missing_photo_deleted = await delete_profile_photo(db, subject="missing-direct-user")
            await db.commit()
            avatar_key = by_key.avatar_key if by_subject else None
            return link_deleted, photo_deleted, missing_photo_deleted, avatar_key

    assert asyncio.run(run()) == (True, True, False, "direct-avatar.png")
