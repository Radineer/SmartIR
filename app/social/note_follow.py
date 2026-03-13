"""note.com auto-follow: discover and follow creators in IR/投資-related tags.

Reuses NoteClient's Playwright browser and authentication pattern.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.post_log import PostLog, PostPlatform, PostType

log = logging.getLogger(__name__)

TARGET_TAGS = ["決算分析", "IR分析", "株式投資", "決算", "日本株", "ファンダメンタル分析"]
MAX_FOLLOWS_PER_DAY = 20
DELAY_MIN = 30
DELAY_MAX = 90


def _get_today_follow_count(db: Session) -> int:
    """Get today's follow count from post_logs."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    return (
        db.query(PostLog)
        .filter(
            PostLog.platform == PostPlatform.NOTE,
            PostLog.metadata_["action"].astext == "follow",
            PostLog.posted_at >= today_start,
        )
        .count()
    )


def _is_already_followed(db: Session, urlname: str) -> bool:
    """Check if user is already followed."""
    return (
        db.query(PostLog)
        .filter(
            PostLog.platform == PostPlatform.NOTE,
            PostLog.metadata_["action"].astext == "follow",
            PostLog.metadata_["target_urlname"].astext == urlname,
        )
        .first()
    ) is not None


async def discover_creators(
    page,
    db: Session,
    tags: list[str] | None = None,
    max_per_tag: int = 10,
) -> list[dict]:
    """Discover creators from note.com hashtag pages.

    Returns list of {urlname, display_name, source_tag}, deduplicated and
    filtered against already-followed users.
    """
    tags = tags or TARGET_TAGS
    seen: set[str] = set()
    creators: list[dict] = []

    for tag in tags:
        url = f"https://note.com/hashtag/{tag}"
        log.info("Scanning tag: %s", tag)

        try:
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            # Scroll down to load more articles
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            # Extract creator links from article cards
            links = await page.query_selector_all('a[href*="/n/"]')
            tag_count = 0

            for link in links:
                if tag_count >= max_per_tag:
                    break

                href = await link.get_attribute("href") or ""
                parts = href.strip("/").split("/")
                if len(parts) >= 3 and parts[-2] == "n":
                    urlname = parts[-3] if len(parts) > 3 else parts[0]
                else:
                    continue

                if not urlname or urlname in seen:
                    continue
                if urlname in ("hashtag", "api", "login", "signup"):
                    continue

                if _is_already_followed(db, urlname):
                    continue

                seen.add(urlname)
                tag_count += 1

                display_name = urlname
                try:
                    name_el = await page.query_selector(
                        f'a[href="/{urlname}"] span, a[href="/{urlname}"]'
                    )
                    if name_el:
                        display_name = (await name_el.text_content() or urlname).strip()
                except Exception:
                    pass

                creators.append({
                    "urlname": urlname,
                    "display_name": display_name,
                    "source_tag": tag,
                })

            log.info("Tag '%s': found %d new creators", tag, tag_count)

        except Exception as e:
            log.warning("Failed to scan tag '%s': %s", tag, e)
            continue

    return creators


async def follow_user(page, urlname: str) -> bool:
    """Follow a user on note.com by visiting their profile."""
    url = f"https://note.com/{urlname}"
    log.info("Visiting profile: %s", url)

    try:
        await page.goto(url)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        follow_btn = page.locator('button:has-text("フォロー")')
        count = await follow_btn.count()

        for i in range(count):
            btn = follow_btn.nth(i)
            text = (await btn.text_content() or "").strip()
            if "フォロー中" in text:
                log.info("Already following %s", urlname)
                return False
            if text == "フォロー" or text == "フォローする":
                await btn.click()
                await asyncio.sleep(2)
                log.info("Followed %s", urlname)
                return True

        log.warning("Follow button not found for %s", urlname)
        return False

    except Exception as e:
        log.warning("Failed to follow %s: %s", urlname, e)
        return False


async def execute_note_follow(
    db: Session,
    max_follows: int = MAX_FOLLOWS_PER_DAY,
    tags: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Execute note.com auto-follow workflow.

    Returns dict with follow results summary.
    """
    today_count = _get_today_follow_count(db)
    remaining = max(0, max_follows - today_count)
    if remaining == 0:
        log.info("Daily follow limit reached (%d/%d)", today_count, max_follows)
        return {
            "discovered": 0,
            "followed": 0,
            "skipped": 0,
            "already_at_limit": True,
        }

    from app.publish.note_client import NoteClient

    async with NoteClient() as client:
        await client.ensure_logged_in()

        if not client._shared_context:
            log.error("Shared browser context not available")
            return {"discovered": 0, "followed": 0, "skipped": 0}

        page = await client._shared_context.new_page()

        try:
            creators = await discover_creators(page, db, tags=tags)
            log.info("Discovered %d new creators", len(creators))

            if dry_run:
                return {
                    "discovered": len(creators),
                    "followed": 0,
                    "skipped": 0,
                    "dry_run": True,
                    "creators": creators,
                }

            random.shuffle(creators)

            followed = 0
            skipped = 0

            for creator in creators:
                if followed >= remaining:
                    log.info("Reached daily limit (%d follows)", followed)
                    break

                urlname = creator["urlname"]
                success = await follow_user(page, urlname)

                if success:
                    post_log = PostLog(
                        platform=PostPlatform.NOTE,
                        post_type=PostType.ANALYSIS,
                        content_preview=f"Followed {urlname}",
                        metadata_={
                            "action": "follow",
                            "target_urlname": urlname,
                            "target_display_name": creator.get("display_name"),
                            "source_tag": creator.get("source_tag"),
                            "date": date.today().isoformat(),
                        },
                    )
                    db.add(post_log)
                    db.commit()

                    followed += 1
                    log.info(
                        "Follow %d/%d: %s (tag: %s)",
                        followed, remaining, urlname, creator.get("source_tag"),
                    )

                    if followed < remaining and followed < len(creators):
                        delay = random.uniform(DELAY_MIN, DELAY_MAX)
                        log.info("Waiting %.0f seconds...", delay)
                        await asyncio.sleep(delay)
                else:
                    skipped += 1

        finally:
            await page.close()

    return {
        "discovered": len(creators),
        "followed": followed,
        "skipped": skipped,
    }
