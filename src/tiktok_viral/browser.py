"""Logged-out browser collection of TikTok hashtag pages, video search and account search (needs the `discover` extra).

Only discovery needs a browser: TikTok's search APIs need parameters that its own JavaScript signs. The item and
user lists the pages load are captured as they arrive; nothing is clicked.

Captcha: a fresh profile gets a slider captcha. With SADCAPTCHA_API_KEY set (paid SadCaptcha service), its
extension solves it; otherwise the tool waits for a person to solve it in the window. The profile is reused.
Account search refuses automated browsers ("Something went wrong"). `stealth=True` hides the automation flag so
it works; that is against TikTok's terms, so it is off by default and the user turns it on knowingly.
Never point this at a logged-in profile.
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from tiktok_viral.web import Account, Item, parse_items, parse_users

PROFILE_ROOT = Path.home() / ".cache" / "tiktok-viral-content" / "browser"
ITEM_APIS = ("/api/challenge/item_list/", "/api/search/item/full/")
USER_API = "/api/search/user/full/"
CAPTCHA = "[id^='captcha-verify-container'], .captcha-verify-container"
SOLVER_KEY = "SADCAPTCHA_API_KEY"
VIEWPORT = {"width": 1280, "height": 900}
SETTLE_MS = 6000
SCROLL_MS = 2000
PAGE_PAUSE_S = 4


@dataclass
class Collected:
    items: list[Item] = field(default_factory=list)
    accounts: list[Account] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def page_urls(tags: list[str], queries: list[str], accounts: list[str]) -> list[tuple[str, str]]:
    user_pages = [(f"user:{a}", f"https://www.tiktok.com/search/user?q={quote(a)}") for a in accounts]
    tag_pages = [(f"tag:{t}", f"https://www.tiktok.com/tag/{quote(t)}") for t in tags]
    query_pages = [(f"q:{q}", f"https://www.tiktok.com/search/video?q={quote(q)}") for q in queries]
    return user_pages + tag_pages + query_pages


def _notify(text: str) -> None:
    print(text, file=sys.stderr)
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f'display notification "{text}" with title "tiktok-viral"'],
                       check=False, capture_output=True)


def _open_context(pw, headless: bool, stealth: bool):
    args = ["--disable-blink-features=AutomationControlled"] if stealth else []
    key = os.environ.get(SOLVER_KEY, "").strip()
    if key:
        from tiktok_captcha_solver import make_playwright_solver_context

        profile = PROFILE_ROOT / "solver"
        profile.mkdir(parents=True, exist_ok=True)
        return make_playwright_solver_context(pw, key, user_data_dir=str(profile), no_warn=True, args=args,
                                              headless=headless, viewport=VIEWPORT)
    profile = PROFILE_ROOT / "plain"
    profile.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(str(profile), headless=headless, viewport=VIEWPORT, args=args)


def _wait_captcha(page, wait_s: int) -> bool:
    if not page.locator(CAPTCHA).count():
        return True
    if wait_s <= 0:
        return False
    who = "the solver has" if os.environ.get(SOLVER_KEY) else "solve it in the browser window within"
    _notify(f"TikTok captcha: {who} {wait_s} s")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if not page.locator(CAPTCHA).count():
            return True
        page.wait_for_timeout(2000)
    return False


def collect(pages: list[tuple[str, str]], scrolls: int = 6, headless: bool = False, captcha_wait: int = 120,
            stealth: bool = False) -> Collected:
    try:
        from playwright.sync_api import Error as PwError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("discovery needs the browser extra: uv sync --extra discover && "
                         "uv run playwright install chromium") from exc
    out = Collected()
    current = {"source": ""}

    def on_response(resp) -> None:
        is_users = USER_API in resp.url
        if not is_users and not any(api in resp.url for api in ITEM_APIS):
            return
        try:
            body = resp.text()
            payload = json.loads(body) if body.strip() else {}
        except (PwError, ValueError) as exc:
            out.problems.append(f"{current['source']}: unreadable response ({str(exc)[:80]})")
            return
        if is_users:
            out.accounts.extend(parse_users(payload, current["source"]))
        else:
            out.items.extend(parse_items(payload, current["source"]))

    with sync_playwright() as pw:
        ctx = _open_context(pw, headless, stealth)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("response", on_response)
        for source, url in pages:
            current["source"] = source
            before = len(out.items) + len(out.accounts)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_timeout(SETTLE_MS)
                had_captcha = page.locator(CAPTCHA).count() > 0
                if not _wait_captcha(page, captcha_wait if (os.environ.get(SOLVER_KEY) or not headless) else 0):
                    out.problems.append(f"{source}: captcha not solved, page skipped")
                    continue
                if had_captcha:
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_timeout(SETTLE_MS)
                for _ in range(0 if source.startswith("user:") else scrolls):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(SCROLL_MS)
                if source.startswith("user:") and "Something went wrong" in page.inner_text("body"):
                    hint = "" if stealth else " (account search needs --stealth)"
                    out.problems.append(f"{source}: account search refused{hint}")
            except PwError as exc:
                out.problems.append(f"{source}: {str(exc)[:120]}")
            print(f"{source}: {len(out.items) + len(out.accounts) - before} results", file=sys.stderr)
            time.sleep(PAGE_PAUSE_S)
        ctx.close()
    return out
