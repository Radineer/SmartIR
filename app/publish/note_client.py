"""note.com client: authentication via Playwright, article publishing via hybrid approach.

Authentication flow:
    1. Playwright opens note.com/login, fills email/password, clicks submit
    2. All cookies are extracted from the browser context
    3. Cookies are saved to disk for reuse

Publishing flow (hybrid API + Playwright):
    1. POST /api/v1/text_notes -- create draft
    2. POST /api/v1/text_notes/draft_save -- save title, body, hashtags
    3. Playwright opens editor.note.com/notes/{key}/edit/ to publish
    4. Editor handles the correct internal format for publishing

Based on boatrace-ai's note_client.py, adapted for SmartIR.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

NOTE_BASE_URL = "https://note.com"
NOTE_EDITOR_BASE = "https://editor.note.com"
NOTE_API_URL = f"{NOTE_BASE_URL}/api/v1/text_notes"
NOTE_LOGIN_URL = f"{NOTE_BASE_URL}/login"

LOGIN_EMAIL_SELECTOR = "#email"
LOGIN_PASSWORD_SELECTOR = "#password"
LOGIN_BUTTON_SELECTOR = ".o-login__button button"

EDITOR_BODY_SELECTOR = ".ProseMirror"

API_HEADERS = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

HTTP_TIMEOUT = 30.0
SESSION_PATH = Path.home() / ".smartir" / "note_session.json"
DEFAULT_PRICE = int(os.getenv("NOTE_DEFAULT_PRICE", "500"))
PUBLISH_INTERVAL = float(os.getenv("PUBLISH_NOTE_INTERVAL", "2"))


class NoteAuthError(Exception):
    pass


class NotePublishError(Exception):
    pass


class NoteClient:
    """Client for note.com: handles login, session management, and article publishing.

    Supports shared browser context for batch publishing (reuse one Playwright
    browser instance across multiple articles) via async context manager.
    """

    def __init__(self, session_path: Path | None = None) -> None:
        self._session_path = session_path or SESSION_PATH
        self._cookies: dict[str, str] = {}
        self._xsrf_token: str = ""
        self._shared_browser = None
        self._shared_context = None
        self._playwright = None

    async def __aenter__(self):
        """Open shared browser context for batch publishing."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._shared_browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            self._shared_context = await self._shared_browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
                locale="ja-JP",
            )
            if self._cookies:
                cookie_list = [
                    {"name": name, "value": value, "domain": ".note.com", "path": "/"}
                    for name, value in self._cookies.items()
                ]
                await self._shared_context.add_cookies(cookie_list)
            log.info("Shared browser context opened for batch publishing")
        except ImportError:
            log.warning("playwright not available, batch mode disabled")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close shared browser context."""
        if self._shared_browser:
            await self._shared_browser.close()
            self._shared_browser = None
            self._shared_context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        log.info("Shared browser context closed")

    def _save_session(self) -> None:
        self._session_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"cookies": self._cookies, "xsrf_token": self._xsrf_token}
        self._session_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        self._session_path.chmod(0o600)
        log.info("Session saved to %s", self._session_path)

    def _load_session(self) -> bool:
        if not self._session_path.exists():
            return False
        try:
            data = json.loads(self._session_path.read_text())
            self._cookies = data["cookies"]
            self._xsrf_token = data["xsrf_token"]
            return True
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("Failed to load session: %s", e)
            return False

    async def _is_session_valid(self) -> bool:
        if not self._cookies:
            return False
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                for path in ("/api/v1/stats/pv_count", "/api/v2/creators/mine"):
                    resp = await client.get(
                        f"{NOTE_BASE_URL}{path}",
                        cookies=self._cookies,
                        headers=API_HEADERS,
                    )
                    if resp.status_code == 200:
                        return True
                    if resp.status_code == 401:
                        return False
                return False
        except httpx.HTTPError as e:
            log.warning("Session validation failed: %s", e)
            return False

    async def _check_captcha_required(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{NOTE_BASE_URL}/api/v3/challenges?via=login")
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    if data.get("challenges", []):
                        log.warning("CAPTCHA required")
                        return True
            return False
        except Exception:
            return False

    async def login(self) -> None:
        """Login to note.com using Playwright and save session cookies."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise NoteAuthError(
                "playwright がインストールされていません。\n"
                "pip install playwright && playwright install chromium"
            )

        email = os.getenv("NOTE_EMAIL")
        password = os.getenv("NOTE_PASSWORD")
        if not email or not password:
            raise NoteAuthError("NOTE_EMAIL と NOTE_PASSWORD を環境変数に設定してください")

        if await self._check_captcha_required():
            log.info("CAPTCHA detected, but Playwright handles invisible reCAPTCHA")

        log.info("Starting Playwright login to note.com...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            try:
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                    locale="ja-JP",
                )
                page = await context.new_page()

                await page.goto(NOTE_BASE_URL)
                await asyncio.sleep(2)

                await page.goto(NOTE_LOGIN_URL)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_selector(LOGIN_EMAIL_SELECTOR, timeout=10000)

                await page.click(LOGIN_EMAIL_SELECTOR)
                await page.keyboard.type(email, delay=50)
                await asyncio.sleep(0.5)
                await page.click(LOGIN_PASSWORD_SELECTOR)
                await page.keyboard.type(password, delay=50)
                await asyncio.sleep(1)

                await page.click(LOGIN_BUTTON_SELECTOR)

                try:
                    await page.wait_for_url(
                        lambda url: url != NOTE_LOGIN_URL and "login" not in url,
                        timeout=15000,
                    )
                except Exception:
                    if "login" in page.url:
                        raise NoteAuthError(
                            "ログインに失敗しました。メールアドレスとパスワードを確認してください。"
                        )

                await page.wait_for_load_state("networkidle")

                cookies = await context.cookies()
                self._cookies = {}
                self._xsrf_token = ""

                for cookie in cookies:
                    if cookie.get("domain", "").endswith("note.com"):
                        self._cookies[cookie["name"]] = cookie["value"]
                    name_lower = cookie["name"].lower()
                    if "xsrf" in name_lower or "csrf" in name_lower:
                        self._xsrf_token = cookie["value"]

                if not self._cookies:
                    raise NoteAuthError("ログイン後にcookieを取得できませんでした。")

                log.info("Login successful. Cookies: %s", ", ".join(sorted(self._cookies.keys())))
                self._save_session()

            finally:
                await browser.close()

    async def ensure_logged_in(self) -> None:
        if self._load_session() and await self._is_session_valid():
            log.info("Existing session is valid")
            return
        log.info("Session invalid or missing, logging in...")
        await self.login()

    async def _create_draft(self) -> dict:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(
                NOTE_API_URL,
                json={"template_key": None},
                cookies=self._cookies,
                headers=API_HEADERS,
            )
            if resp.status_code not in (200, 201):
                raise NotePublishError(
                    f"下書き作成に失敗しました (HTTP {resp.status_code}): {resp.text[:200]}"
                )
            data = resp.json().get("data", {})
            draft_id = data.get("id")
            draft_key = data.get("key")
            if not draft_id or not draft_key:
                raise NotePublishError(f"下書きIDの取得に失敗しました: {data}")
            log.info("Draft created: id=%s, key=%s", draft_id, draft_key)
            return {"id": draft_id, "key": draft_key}

    async def _save_draft_content(
        self,
        draft_id: int,
        title: str,
        html_body: str,
        hashtags: list[str] | None = None,
    ) -> None:
        payload: dict[str, object] = {"name": title, "body": html_body}
        if hashtags:
            payload["hashtags"] = hashtags

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(
                f"{NOTE_API_URL}/draft_save?id={draft_id}",
                json=payload,
                cookies=self._cookies,
                headers=API_HEADERS,
            )
            if resp.status_code not in (200, 201):
                raise NotePublishError(
                    f"下書き保存に失敗しました (HTTP {resp.status_code}): {resp.text[:200]}"
                )
            log.info("Draft content saved (id=%s)", draft_id)

    async def _dismiss_modals(self, page) -> None:
        """Dismiss any popup modals/dialogs that might block interaction."""
        modal_close_selectors = [
            'button[aria-label="閉じる"]',
            'button[aria-label="Close"]',
            'button:has-text("閉じる")',
            'button:has-text("OK")',
            'button:has-text("あとで")',
            '[class*="modal"] button[class*="close"]',
            '[class*="dialog"] button[class*="close"]',
        ]
        for selector in modal_close_selectors:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    await el.click()
                    await asyncio.sleep(0.5)
                    log.info("Dismissed modal via: %s", selector)
            except Exception:
                pass

    async def _set_eyecatch(self, page, eyecatch_path: str) -> None:
        """Set the eyecatch (OGP) image on the publish settings page.

        Tries multiple approaches:
        1. Standard file input
        2. CDP-based file chooser (for hidden inputs)
        3. Label-based discovery
        """
        await self._dismiss_modals(page)

        try:
            # Approach 1: Direct file input
            file_input = await page.query_selector('input[type="file"]')

            # Approach 2: Try finding via label
            if not file_input:
                labels = await page.query_selector_all("label")
                for label in labels:
                    text = (await label.text_content() or "").strip()
                    if "見出し画像" in text or "アイキャッチ" in text or "画像" in text:
                        file_input = await label.query_selector('input[type="file"]')
                        if file_input:
                            break

            if file_input:
                await file_input.set_input_files(eyecatch_path)
                await asyncio.sleep(3)
                log.info("Eyecatch image set: %s", eyecatch_path)
                # Dismiss any crop/edit modal that may appear
                await self._dismiss_modals(page)
            else:
                # Approach 3: CDP file chooser for dynamically created inputs
                try:
                    eyecatch_btn = await page.query_selector('[class*="eyecatch"], [class*="thumbnail"]')
                    if eyecatch_btn:
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await eyecatch_btn.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(eyecatch_path)
                        await asyncio.sleep(3)
                        log.info("Eyecatch image set via file chooser: %s", eyecatch_path)
                        await self._dismiss_modals(page)
                    else:
                        log.warning("Eyecatch file input not found")
                except Exception as e2:
                    log.warning("CDP file chooser also failed: %s", e2)
        except Exception as e:
            log.warning("Failed to set eyecatch image: %s", e)

    async def _publish_via_editor(
        self,
        draft_key: str,
        price: int,
        hashtags: list[str] | None = None,
        eyecatch_path: str | None = None,
    ) -> dict:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise NotePublishError("playwright が必要です")

        editor_url = f"{NOTE_EDITOR_BASE}/notes/{draft_key}/edit/"
        log.info("Opening editor: %s", editor_url)

        result: dict[str, object] = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            try:
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                    locale="ja-JP",
                )

                cookie_list = [
                    {"name": name, "value": value, "domain": ".note.com", "path": "/"}
                    for name, value in self._cookies.items()
                ]
                await context.add_cookies(cookie_list)

                page = await context.new_page()

                publish_response: dict = {}

                async def on_response(response):
                    url = response.url
                    if "/api/" in url and ("text_notes" in url or "notes" in url):
                        method = response.request.method
                        status = response.status
                        if method in ("PUT", "POST") and status in (200, 201):
                            try:
                                body = await response.json()
                                publish_response["status"] = status
                                publish_response["data"] = body
                                publish_response["url"] = url
                            except Exception:
                                pass

                page.on("response", on_response)

                await page.goto(editor_url)
                await asyncio.sleep(3)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(3)

                try:
                    await page.wait_for_selector(EDITOR_BODY_SELECTOR, timeout=15000)
                except Exception:
                    raise NotePublishError(
                        "エディタが読み込めませんでした。セッションが無効かもしれません。"
                    )

                # Dismiss any modals before proceeding
                await self._dismiss_modals(page)

                # Click "公開に進む"
                publish_btn = await self._find_button(page, ["公開に進む", "公開設定", "公開"])
                if not publish_btn:
                    raise NotePublishError("公開ボタンが見つかりませんでした。")

                await publish_btn.click()
                await asyncio.sleep(3)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)

                if eyecatch_path:
                    await self._set_eyecatch(page, eyecatch_path)

                if hashtags:
                    await self._set_hashtags(page, hashtags)

                if price > 0:
                    await self._set_paid_settings(page, price)

                # Dismiss any modals before final publish
                await self._dismiss_modals(page)

                # Click "投稿する"
                final_btn = await self._find_button(page, ["投稿する", "投稿", "公開する", "公開"])
                if not final_btn:
                    raise NotePublishError("投稿ボタンが見つかりませんでした。")

                await final_btn.click()
                await asyncio.sleep(5)

                result["draft_key"] = draft_key
                if publish_response:
                    result["api_response"] = publish_response
                    put_data = publish_response.get("data", {})
                    if isinstance(put_data, dict):
                        data_inner = put_data.get("data", put_data)
                        user = data_inner.get("user", {})
                        urlname = user.get("urlname", "")
                        key = data_inner.get("key", draft_key)
                        if urlname:
                            result["note_url"] = f"{NOTE_BASE_URL}/{urlname}/n/{key}"
                        else:
                            result["note_url"] = f"{NOTE_BASE_URL}/n/{key}"

                if "note_url" not in result:
                    result["note_url"] = f"{NOTE_BASE_URL}/n/{draft_key}"

                log.info("Publish complete. note_url=%s", result.get("note_url"))

            finally:
                await browser.close()

        return result

    async def _find_button(self, page, text_options: list[str]):
        for text in text_options:
            try:
                btn = page.get_by_role("button", name=text)
                if await btn.count() > 0 and await btn.first.is_visible():
                    return btn.first
            except Exception:
                pass

        buttons = await page.query_selector_all("button")
        for btn in buttons:
            if await btn.is_visible():
                btn_text = (await btn.text_content() or "").strip()
                for text in text_options:
                    if text in btn_text:
                        return btn
        return None

    async def _set_hashtags(self, page, hashtags: list[str]) -> None:
        try:
            tag_tab = await self._find_button(page, ["ハッシュタグ"])
            if tag_tab:
                await tag_tab.click()
                await asyncio.sleep(1)

            inp = await page.query_selector('input[placeholder="ハッシュタグを追加する"]')
            if not inp:
                log.warning("Hashtag input not found")
                return

            for tag in hashtags:
                await inp.click()
                await inp.fill(tag)
                await asyncio.sleep(0.3)
                await inp.press("Enter")
                await asyncio.sleep(0.5)

            log.info("Set %d hashtags", len(hashtags))
        except Exception as e:
            log.warning("Failed to set hashtags: %s", e)

    async def _set_paid_settings(self, page, price: int) -> None:
        try:
            type_tab = await self._find_button(page, ["記事タイプ"])
            if type_tab:
                await type_tab.click()
                await asyncio.sleep(1)

            paid_clicked = False
            for selector in [
                "button:has-text('有料')",
                "text=有料",
                "label:has-text('有料')",
                "[role='radio']:has-text('有料')",
            ]:
                try:
                    el = await page.query_selector(selector)
                    if el and await el.is_visible():
                        await el.click()
                        await asyncio.sleep(1)
                        paid_clicked = True
                        break
                except Exception:
                    pass

            if not paid_clicked:
                log.warning("有料 option not found -- article will be free")
                return

            inputs = await page.query_selector_all("input")
            for inp in inputs:
                if await inp.is_visible():
                    inp_type = await inp.get_attribute("type") or ""
                    placeholder = await inp.get_attribute("placeholder") or ""
                    if inp_type == "number" or "円" in placeholder or "価格" in placeholder:
                        await inp.click()
                        await inp.fill(str(price))
                        await asyncio.sleep(0.5)
                        log.info("Price set to %d yen", price)
                        break
        except Exception as e:
            log.warning("Failed to set paid settings: %s", e)

    async def create_and_publish(
        self,
        title: str,
        html_body: str,
        price: int | None = None,
        hashtags: list[str] | None = None,
        eyecatch_path: str | None = None,
        article_type: str | None = None,
    ) -> dict:
        """Create and publish an article on note.com.

        Args:
            title: Article title
            html_body: HTML body content (with <pay> tag for paid section)
            price: Price in JPY (0 = free, default from NOTE_DEFAULT_PRICE)
            hashtags: List of hashtag strings
            eyecatch_path: Path to eyecatch image. If None and article_type is set,
                          auto-generates using eyecatch module.
            article_type: Article type for auto eyecatch generation
                         (breaking, analysis, daily_summary, industry, weekly_trend, earnings_calendar)

        Returns:
            Dict containing publish result info including note_url.
        """
        if price is None:
            price = DEFAULT_PRICE

        log.info("Publishing article: %s (price=%d yen)", title, price)

        # Auto-generate eyecatch if not provided
        if eyecatch_path is None and article_type:
            try:
                from app.publish.eyecatch import generate_eyecatch
                path = await generate_eyecatch(title, article_type)
                if path:
                    eyecatch_path = str(path)
            except Exception as e:
                log.warning("Eyecatch auto-generation failed: %s", e)

        draft = await self._create_draft()
        await self._save_draft_content(draft["id"], title, html_body, hashtags)

        try:
            result = await self._publish_via_editor(
                draft["key"], price, hashtags, eyecatch_path,
            )
        except Exception as e:
            log.error("Playwright publish failed: %s", e)
            raise NotePublishError(
                f"記事の公開に失敗しました: {e}\n"
                f"下書きは保存されています (key={draft['key']})"
            ) from e

        return result

    async def get_status(self) -> dict[str, object]:
        session_exists = self._session_path.exists()
        loaded = self._load_session() if session_exists else False
        valid = await self._is_session_valid() if loaded else False
        return {
            "logged_in": valid,
            "session_path": str(self._session_path),
            "session_exists": session_exists,
        }
