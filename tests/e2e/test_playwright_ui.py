from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

CSS = Path("app/static/css/app.css").read_text(encoding="utf-8")
JAVASCRIPT = Path("app/static/js/app.js").read_text(encoding="utf-8")


def _render(page: Page, html: str) -> None:
    isolated = re.sub(r"<link\b[^>]*>", "", html, flags=re.IGNORECASE)
    isolated = re.sub(r"<script\b[^>]*\bsrc=[^>]*></script>", "", isolated, flags=re.IGNORECASE)
    page.set_content(isolated, wait_until="domcontentloaded", timeout=10_000)
    page.add_style_tag(content=CSS)
    page.add_script_tag(content=JAVASCRIPT)


@pytest.mark.e2e
def test_public_error_page_responsive_with_system_chromium(client) -> None:
    response = client.get("/auth/error")
    assert response.status_code == 400
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "/usr/bin/chromium")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=executable,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        for width, height in ((390, 844), (768, 1024), (1440, 900)):
            page = browser.new_page(viewport={"width": width, "height": height})
            _render(page, response.text)
            assert page.locator("main").is_visible()
            assert page.locator("h1").is_visible()
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement !== document.body")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            page.close()
        browser.close()


@pytest.mark.e2e
def test_authenticated_account_flows_render_and_progressively_enhance(client, login_user) -> None:
    login_user(subject="browser-user")
    paths = ("/", "/profile", "/sessions", "/services", "/preferences")
    pages = {path: client.get(path).text for path in paths}
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "/usr/bin/chromium")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=executable,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_default_timeout(3000)
            _render(page, pages["/"])
            assert page.locator("h1").filter(has_text="Welcome, Raj Test").is_visible()
            page.locator("[data-command-open]").click()
            assert page.locator("[data-command-palette]").is_visible()
            page.locator("[data-command-input]").fill("security")
            assert page.locator("[data-command-item]:visible").count() >= 1
            page.keyboard.press("Escape")
            assert page.locator("[data-command-palette]").is_hidden()
            page.locator("[data-nav-toggle]").click()
            assert page.locator("#mobile-nav").is_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

            _render(page, pages["/profile"])
            assert page.locator('input[name="display_name"]').input_value() == "Raj Test"
            assert (
                page.locator('button[type="submit"]').filter(has_text="Save profile").is_visible()
            )

            _render(page, pages["/preferences"])
            page.locator('input[name="theme"][value="dark"]').check(force=True)
            assert page.locator("html").get_attribute("data-theme") == "dark"

            _render(page, pages["/services"])
            assert page.get_by_text("Reference-only service history").is_visible()
            assert page.get_by_text("Disconnect", exact=True).count() == 0

            _render(page, pages["/sessions"])
            result = page.evaluate(
                """() => {
                    window.confirm = () => false;
                    const form = document.querySelector('form[data-confirm]');
                    const event = new Event('submit', {bubbles: true, cancelable: true});
                    const dispatched = form.dispatchEvent(event);
                    return {dispatched, prevented: event.defaultPrevented};
                }"""
            )
            assert result == {"dispatched": False, "prevented": True}
        finally:
            browser.close()
