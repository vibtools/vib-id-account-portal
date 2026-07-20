from __future__ import annotations


def test_profile_avatar_social_and_portable_api(client, login_user) -> None:
    login = login_user(subject="portable-profile-user", display_name="Portable User")
    png_payload = b"\x89PNG\r\n\x1a\n" + b"safe-test-avatar"

    avatar_response = client.post(
        "/profile/avatar",
        data={"csrf_token": login.csrf_token},
        files={"photo": ("avatar.png", png_payload, "image/png")},
        follow_redirects=False,
    )
    assert avatar_response.status_code == 303

    link_response = client.post(
        "/profile/social-links",
        data={
            "csrf_token": login.csrf_token,
            "platform": "github",
            "label": "GitHub",
            "url": "https://github.com/vibtools",
            "visibility": "apps",
        },
        follow_redirects=False,
    )
    assert link_response.status_code == 303

    profile = client.get("/api/account/profile/portable")
    assert profile.status_code == 200
    payload = profile.json()
    assert payload["subject"] == login.subject
    assert payload["avatar_url"].startswith("http://testserver/media/profile-avatars/")
    assert payload["social_links"][0]["platform"] == "github"

    avatar = client.get(payload["avatar_url"].replace("http://testserver", ""))
    assert avatar.status_code == 200
    assert avatar.content == png_payload
    assert avatar.headers["content-type"].startswith("image/png")

    internal = client.get(
        f"/internal/v1/account-profiles/{login.subject}",
        headers={"authorization": "Bearer valid-service-token"},
    )
    assert internal.status_code == 200
    assert internal.json()["avatar_url"] == payload["avatar_url"]


def test_applications_page_uses_central_ygit_session(client, login_user) -> None:
    login_user(subject="central-app-user")

    class CentralYgitKeycloak:
        async def list_user_sessions(self, subject: str) -> list[dict[str, object]]:
            del subject
            return [
                {
                    "id": "central-session",
                    "clients": {"ygit": "YGIT", "vib-id-portal": "Vib ID"},
                    "lastAccess": 1_771_432_800_000,
                }
            ]

    client.app.state.keycloak = CentralYgitKeycloak()
    page = client.get("/applications")
    assert page.status_code == 200
    assert "YGIT" in page.text
    assert "ygit.net" in page.text

    api = client.get("/api/applications")
    assert api.status_code == 200
    assert api.json()["applications"][0]["service_key"] == "ygit"


def test_account_experience_rejects_invalid_media_and_internal_access(client, login_user) -> None:
    login = login_user(subject="invalid-media-user")

    empty = client.post(
        "/profile/avatar",
        data={"csrf_token": login.csrf_token},
        files={"photo": ("empty.png", b"", "image/png")},
    )
    assert empty.status_code == 422
    assert "file is empty" in empty.text

    wrong_signature = client.post(
        "/profile/avatar",
        data={"csrf_token": login.csrf_token},
        files={"photo": ("avatar.png", b"not-a-png", "image/png")},
    )
    assert wrong_signature.status_code == 422
    assert "format is not supported" in wrong_signature.text

    wrong_type = client.post(
        "/profile/avatar",
        data={"csrf_token": login.csrf_token},
        files={"photo": ("avatar.svg", b"<svg></svg>", "image/svg+xml")},
    )
    assert wrong_type.status_code == 422
    assert "PNG, JPEG, or WebP" in wrong_type.text

    assert client.get("/media/profile-avatars/../../bad").status_code == 404
    assert client.get("/media/profile-avatars/not-found.png").status_code == 404
    assert client.get(f"/internal/v1/account-profiles/{login.subject}").status_code == 401
    assert client.get(
        f"/internal/v1/account-profiles/{login.subject}",
        headers={"authorization": "Bearer invalid-service-token"},
    ).status_code == 403
    assert client.get(
        "/internal/v1/account-profiles/bad/subject",
        headers={"authorization": "Bearer valid-service-token"},
    ).status_code == 404


def test_social_private_visibility_and_delete(client, login_user) -> None:
    login = login_user(subject="social-private-user")
    private = client.post(
        "/profile/social-links",
        data={
            "csrf_token": login.csrf_token,
            "platform": "linkedin",
            "label": "LinkedIn",
            "url": "https://www.linkedin.com/company/vibtools",
            "visibility": "private",
        },
        follow_redirects=False,
    )
    assert private.status_code == 303
    portable = client.get("/api/account/profile/portable")
    assert portable.status_code == 200
    assert portable.json()["social_links"] == []

    page = client.get("/profile")
    assert "LinkedIn" in page.text
    import re

    match = re.search(r'/profile/social-links/([^/]+)/delete', page.text)
    assert match is not None
    delete_response = client.post(
        f"/profile/social-links/{match.group(1)}/delete",
        data={"csrf_token": login.csrf_token},
        follow_redirects=False,
    )
    assert delete_response.status_code == 303

    missing_delete = client.post(
        f"/profile/social-links/{match.group(1)}/delete",
        data={"csrf_token": login.csrf_token},
        follow_redirects=False,
    )
    assert missing_delete.status_code == 404


def test_avatar_delete_and_size_limit(client, login_user) -> None:
    login = login_user(subject="avatar-delete-user")
    png_payload = b"\x89PNG\r\n\x1a\n" + b"avatar"
    assert client.post(
        "/profile/avatar",
        data={"csrf_token": login.csrf_token},
        files={"photo": ("avatar.png", png_payload, "image/png")},
        follow_redirects=False,
    ).status_code == 303
    oversized = b"\x89PNG\r\n\x1a\n" + (
        b"x" * (client.app.state.settings.PROFILE_AVATAR_MAX_BYTES + 1)
    )
    too_large = client.post(
        "/profile/avatar",
        data={"csrf_token": login.csrf_token},
        files={"photo": ("avatar.png", oversized, "image/png")},
    )
    assert too_large.status_code == 422
    assert "larger" in too_large.text
    removed = client.post(
        "/profile/avatar/delete",
        data={"csrf_token": login.csrf_token},
        follow_redirects=False,
    )
    assert removed.status_code == 303
    assert client.get("/api/account/profile/portable").json()["avatar_url"] is None


def test_account_experience_additional_error_paths(client, login_user) -> None:
    login = login_user(subject="error-path-user")
    mismatch = client.post(
        "/profile/avatar",
        data={"csrf_token": login.csrf_token},
        files={"photo": ("avatar.jpg", b"\x89PNG\r\n\x1a\nreal-png", "image/jpeg")},
    )
    assert mismatch.status_code == 422
    assert "does not match" in mismatch.text
    assert client.get("/media/profile-avatars/bad..key").status_code == 404
    assert client.get(
        "/internal/v1/account-profiles/ab",
        headers={"authorization": "Bearer valid-service-token"},
    ).status_code == 400


def test_account_experience_profile_overview_and_contacts(client, login_user) -> None:
    login = login_user(subject="profile-form-user", email_verified=False)
    overview = client.get("/")
    assert overview.status_code == 200
    assert "Complete your profile" in overview.text

    profile_page = client.get("/profile")
    assert profile_page.status_code == 200
    assert "VibTools profile" in profile_page.text

    invalid_profile = client.post(
        "/profile",
        data={
            "csrf_token": login.csrf_token,
            "display_name": "",
            "timezone": "UTC",
            "preferred_language": "en",
            "version": "bad-version",
        },
    )
    assert invalid_profile.status_code == 422

    version = profile_page.text.split('name="version" value="')[1].split('"')[0]
    valid_profile = client.post(
        "/profile",
        data={
            "csrf_token": login.csrf_token,
            "display_name": "Profile Form User",
            "phone_country_code": "+1",
            "phone_number": "+14155552671",
            "country_code": "US",
            "timezone": "UTC",
            "preferred_language": "en",
            "organization_name": "VibTools",
            "job_title": "Engineer",
            "version": version,
        },
        follow_redirects=False,
    )
    assert valid_profile.status_code in {303, 422}

    invalid_contact = client.post(
        "/profile/contacts",
        data={
            "csrf_token": login.csrf_token,
            "contact_type": "email",
            "label": "Work",
            "value": "not-an-email",
        },
    )
    assert invalid_contact.status_code == 422

    contact = client.post(
        "/profile/contacts",
        data={
            "csrf_token": login.csrf_token,
            "contact_type": "website",
            "label": "Website",
            "value": "https://vib.tools",
            "is_primary": "on",
        },
        follow_redirects=False,
    )
    assert contact.status_code == 303
    page = client.get("/profile")
    import re

    match = re.search(r'/profile/contacts/([^/]+)/delete', page.text)
    assert match is not None
    assert client.post(
        f"/profile/contacts/{match.group(1)}/delete",
        data={"csrf_token": login.csrf_token},
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        f"/profile/contacts/{match.group(1)}/delete",
        data={"csrf_token": login.csrf_token},
        follow_redirects=False,
    ).status_code == 404


def test_profile_page_hides_developer_api_preview(client, login_user) -> None:
    login_user(subject="profile-ui-hotfix-user")
    page = client.get("/profile")
    assert page.status_code == 200
    assert "Preview portable profile API" not in page.text
    assert "/api/account/profile/portable" not in page.text
    assert "VibTools profile" in page.text


def test_applications_page_shows_catalog_without_history_and_maps_backend_aliases(
    client, login_user
) -> None:
    login_user(subject="app-catalog-hotfix-user")

    class BackendAliasKeycloak:
        async def list_user_sessions(self, subject: str) -> list[dict[str, object]]:
            del subject
            return [
                {
                    "id": "central-ygit-dev-session",
                    "clients": {
                        "service-account-ygit-dev-backend": "YGIT Dev Backend",
                        "vib-id-portal": "Vib ID",
                    },
                    "lastAccess": 1_771_432_800_000,
                }
            ]

    client.app.state.keycloak = BackendAliasKeycloak()
    page = client.get("/applications")
    assert page.status_code == 200
    assert "App catalog" in page.text
    assert "YGIT" in page.text
    assert "ygit.net" in page.text
    assert "YGIT Dev" in page.text
    assert "ygit.dev" in page.text
    assert "Connected" in page.text

    api = client.get("/api/applications")
    assert api.status_code == 200
    assert api.json()["applications"][0]["service_key"] == "ygit-dev"


def test_account_data_export_txt_and_csv_do_not_expose_tokens(client, login_user) -> None:
    login = login_user(subject="account-export-user", display_name="Export User")
    client.post(
        "/profile/social-links",
        data={
            "csrf_token": login.csrf_token,
            "platform": "website",
            "label": "Website",
            "url": "https://vib.tools",
            "visibility": "apps",
        },
        follow_redirects=False,
    )

    txt_response = client.get("/preferences/account-data.txt")
    assert txt_response.status_code == 200
    assert "attachment" in txt_response.headers["content-disposition"]
    assert "Vib ID Account Data Export" in txt_response.text
    assert "Export User" in txt_response.text
    assert "https://vib.tools" in txt_response.text
    assert "access_token" not in txt_response.text
    assert "csrf" not in txt_response.text.lower()

    csv_response = client.get("/preferences/account-data.csv")
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "section,field,value" in csv_response.text
    assert "Export User" in csv_response.text
    assert "server-only-access-token" not in csv_response.text
