"""X engagement strategy: quote repost + reply chain for IR analysis growth.

Based on X's public algorithm weights:
  - Reply chain (相手が返信) = 75x  ← 最重要
  - Reply                    = 13.5x
  - Quote repost             ≈ 25x
  - Repost                   = 1x
  - Like                     = 0.5x
  - Negative (block/mute)    = -74x  ← 絶対に回避

Growth strategy:
  1. 引用RTで大手に通知 → リポスト返しで露出獲得
  2. リプライで会話チェーン → 75x重み
  3. Real Graph構築 → 毎日の継続エンゲージで相互認知
  4. 投稿後30分が勝負 → 早期エンゲージがリーチを決定
"""

from __future__ import annotations

import logging
import random
import time
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.post_log import PostLog, PostPlatform, PostType

log = logging.getLogger(__name__)

# ── Target accounts (IR/投資系) ─────────────────────────

TARGET_ACCOUNTS = [
    {"handle": "bufflobal", "name": "バフェット太郎", "priority": "S"},
    {"handle": "stockclimb", "name": "株クライマー", "priority": "A"},
    {"handle": "kabumatome", "name": "株まとめ", "priority": "A"},
    {"handle": "stock_and_info", "name": "決算情報", "priority": "A"},
    {"handle": "ir_analysis_jp", "name": "IR分析", "priority": "B"},
]

PRIORITY_ORDER = {"S": 0, "A": 1, "B": 2}

# ── Rate limits (daily) ─────────────────────────────────

MAX_QUOTES_PER_DAY = 8
MAX_REPLIES_PER_DAY = 20
MAX_LIKES_PER_DAY = 40
MAX_QUOTES_PER_HANDLE_PER_DAY = 2

# ── Humanization parameters ─────────────────────────────

TARGET_ENGAGE_PROB = 0.75
LIKE_PROB = 0.7
BOTH_QUOTE_AND_REPLY_PROB = 0.5
ACTION_DELAY_MIN = 3
ACTION_DELAY_MAX = 10

# ── Text variation ──────────────────────────────────────

_FILLERS = ["", "なるほど、", "おお、", "これは、"]
_TRAIL_VARIATIONS = ["", " 注目してます", " 参考になります", " 気になりますね"]
_EMOJI_POOL = ["", "", "", "", " ✨", " 📊", " 🔥", " 💡", " 📈"]

# ── Quote templates (IR domain) ──────────────────────────

QUOTE_TEMPLATES_POSITIVE = [
    "好決算! SmartIRのAI分析でもポジティブ判定でした。データが一致すると堅いですね\n\nどのセグメントに注目されてますか？",
    "見事な業績! SmartIRのセンチメント分析でもこの銘柄は高評価\n\n決算短信のどこを一番重視されてますか？",
    "ナイス分析! SmartIRのAIでも同じ結論でした\n\nやっぱりファンダメンタルがしっかりしてると安心感ありますね",
]

QUOTE_TEMPLATES_ANALYSIS = [
    "SmartIRのAI分析でも同銘柄を注目中。センチメントスコアが高めです\n\n根拠のある分析は参考になりますね #IR分析",
    "同意です。SmartIRだとセンチメント分析で別角度から見てますが、結論は同じでした\n\n#決算分析 #IR分析",
    "なるほど、この視点は面白い。SmartIRのAI分析では少し違う角度で見てましたが参考になります\n\n#決算 #IR分析",
]

QUOTE_TEMPLATES_INFO = [
    "SmartIRでもこの銘柄注目してます。AI分析で全銘柄のセンチメントスコアを配信中\n\n#決算 #IR分析",
    "この決算、SmartIRのAI分析では注目度高いです。データ的に見どころ多いですね\n\n#IR分析",
]

QUOTE_TEMPLATES = QUOTE_TEMPLATES_POSITIVE + QUOTE_TEMPLATES_ANALYSIS + QUOTE_TEMPLATES_INFO

REPLY_TEMPLATES_CONVERSATION = [
    "注目決算ですね! AI分析的にも面白い結果が出てます。セグメント別ではどこが気になりますか？",
    "さすがの分析ですね。SmartIRのAIでも同じ結論でした。来期予想はどう見てますか？",
    "同じく注目してました! 今期の業績修正、AI分析的にはポジティブ寄りでした。どう評価されてますか？",
    "面白い視点ですね。SmartIRだと少し違う結論なんですが、決算説明資料は確認されましたか？",
]

REPLY_TEMPLATES_PRAISE = [
    "いつも的確な分析で参考にしてます。IR分析やってる身として勉強になります",
    "さすがです。この決算は難しかったのに見事な読みですね",
    "いつも勉強になります。ファンダメンタル分析の精度、本当にすごい",
]

REPLY_TEMPLATES = REPLY_TEMPLATES_CONVERSATION + REPLY_TEMPLATES_PRAISE

# ── Keyword filters ─────────────────────────────────────

IR_KEYWORDS = [
    "決算", "IR", "業績", "四半期", "増収", "増益", "減収", "減益",
    "上方修正", "下方修正", "経常利益", "営業利益", "売上高",
    "配当", "自社株買い", "株主還元", "決算短信", "有報",
]

POSITIVE_KEYWORDS = ["増収", "増益", "上方修正", "好決算", "最高益", "増配"]
ANALYSIS_KEYWORDS = ["分析", "予想", "注目", "考察", "評価", "IR"]


def _is_ir_related(text: str) -> bool:
    """Check if tweet text is IR-related."""
    return any(kw in text for kw in IR_KEYWORDS)


def _classify_tweet(text: str) -> str:
    """Classify tweet as 'positive', 'analysis', or 'info'."""
    if any(kw in text for kw in POSITIVE_KEYWORDS):
        return "positive"
    if any(kw in text for kw in ANALYSIS_KEYWORDS):
        return "analysis"
    return "info"


def _humanize_text(text: str) -> str:
    """Add subtle randomness to text so it doesn't look automated."""
    if random.random() < 0.3:
        filler = random.choice(_FILLERS)
        if filler:
            text = filler + text

    if random.random() < 0.2:
        trail = random.choice(_TRAIL_VARIATIONS)
        if trail:
            text = text.rstrip() + trail

    if random.random() < 0.15:
        emoji = random.choice(_EMOJI_POOL)
        if emoji:
            text = text.rstrip() + emoji

    return text


def _human_delay(dry_run: bool = False) -> None:
    """Random delay between actions to appear human."""
    if dry_run:
        return
    delay = random.uniform(ACTION_DELAY_MIN, ACTION_DELAY_MAX)
    time.sleep(delay)


def get_sorted_targets(priority_filter: str | None = None) -> list[dict]:
    """Get target accounts sorted by priority (S > A > B)."""
    targets = TARGET_ACCOUNTS
    if priority_filter:
        targets = [t for t in targets if t["priority"] == priority_filter]
    return sorted(targets, key=lambda t: PRIORITY_ORDER.get(t["priority"], 99))


def _get_engagement_count(db: Session, target_date: str, action_type: str) -> int:
    """Get engagement count for a date and action type from post_logs."""
    today_start = datetime.fromisoformat(f"{target_date}T00:00:00")
    return (
        db.query(PostLog)
        .filter(
            PostLog.platform == PostPlatform.TWITTER,
            PostLog.metadata_["engagement_type"].astext == action_type,
            PostLog.posted_at >= today_start,
        )
        .count()
    )


def can_quote(db: Session, race_date: str) -> bool:
    return _get_engagement_count(db, race_date, "quote") < MAX_QUOTES_PER_DAY


def can_reply(db: Session, race_date: str) -> bool:
    return _get_engagement_count(db, race_date, "reply") < MAX_REPLIES_PER_DAY


def can_like(db: Session, race_date: str) -> bool:
    return _get_engagement_count(db, race_date, "like") < MAX_LIKES_PER_DAY


def pick_quote_template(tweet_text: str = "") -> str:
    """Pick a quote template matched to the tweet content, with humanization."""
    category = _classify_tweet(tweet_text)
    if category == "positive":
        text = random.choice(QUOTE_TEMPLATES_POSITIVE)
    elif category == "analysis":
        text = random.choice(QUOTE_TEMPLATES_ANALYSIS)
    else:
        text = random.choice(QUOTE_TEMPLATES_INFO)
    return _humanize_text(text)


def pick_reply_template(tweet_text: str = "") -> str:
    """Pick a reply template. Prioritize conversation starters (75x weight)."""
    if random.random() < 0.7:
        text = random.choice(REPLY_TEMPLATES_CONVERSATION)
    else:
        text = random.choice(REPLY_TEMPLATES_PRAISE)
    return _humanize_text(text)


def scan_targets(
    target_handle: str | None = None,
    max_tweets_per_target: int = 5,
) -> list[dict]:
    """Scan target accounts for recent IR-related tweets."""
    from app.social.twitter import TwitterClient

    targets = get_sorted_targets()
    if target_handle:
        targets = [t for t in targets if t["handle"] == target_handle]

    client = TwitterClient()
    results = []
    for target in targets:
        tweets = client.get_user_recent_tweets(target["handle"], max_results=max_tweets_per_target)
        relevant = [t for t in tweets if _is_ir_related(t["text"])]
        if relevant:
            results.append({
                "handle": target["handle"],
                "name": target["name"],
                "priority": target["priority"],
                "tweets": relevant,
            })
    return results


def execute_engagement(
    db: Session,
    dry_run: bool = False,
) -> dict:
    """Execute auto engagement routine with human-like randomness.

    Returns summary dict with counts of actions taken.
    """
    from app.social.twitter import TwitterClient

    target_date = date.today().isoformat()
    summary = {"quotes": 0, "replies": 0, "likes": 0, "skipped": 0}

    scan_results = scan_targets()
    if not scan_results:
        log.info("No IR-related tweets found from targets")
        return summary

    random.shuffle(scan_results)
    client = TwitterClient()

    for target_data in scan_results:
        handle = target_data["handle"]
        tweets = target_data["tweets"]

        if not tweets:
            continue

        # Random chance to skip this target
        if random.random() > TARGET_ENGAGE_PROB:
            log.info("Randomly skipping target @%s this run", handle)
            summary["skipped"] += 1
            continue

        # Like tweets randomly
        shuffled_tweets = list(tweets)
        random.shuffle(shuffled_tweets)
        for tweet in shuffled_tweets:
            if not can_like(db, target_date):
                break
            if random.random() > LIKE_PROB:
                continue
            _human_delay(dry_run)
            liked = client.like_tweet(tweet["id"], dry_run=dry_run)
            if liked:
                summary["likes"] += 1

        # Pick the best tweet for quote RT
        best_tweet = max(
            tweets,
            key=lambda t: t.get("metrics", {}).get("like_count", 0)
            + t.get("metrics", {}).get("retweet_count", 0) * 2,
        )

        do_quote = can_quote(db, target_date)
        do_reply = can_reply(db, target_date)
        do_both = random.random() < BOTH_QUOTE_AND_REPLY_PROB

        if do_quote and do_reply and not do_both:
            if random.random() < 0.6:
                do_reply = False
            else:
                do_quote = False

        # Quote RT
        if do_quote:
            _human_delay(dry_run)
            text = pick_quote_template(best_tweet["text"])
            our_id = client.quote_repost(best_tweet["id"], text, dry_run=dry_run)
            if our_id or dry_run:
                if not dry_run and our_id:
                    post_log = PostLog(
                        platform=PostPlatform.TWITTER,
                        post_type=PostType.ANALYSIS,
                        external_id=our_id,
                        content_preview=text[:200],
                        metadata_={
                            "engagement_type": "quote",
                            "target_handle": handle,
                            "target_tweet_id": best_tweet["id"],
                            "date": target_date,
                        },
                    )
                    db.add(post_log)
                    db.commit()
                summary["quotes"] += 1

        # Reply
        if do_reply:
            _human_delay(dry_run)
            reply_tweet = tweets[1] if len(tweets) > 1 else best_tweet
            text = pick_reply_template(reply_tweet["text"])
            reply_id = client.reply_to_tweet(reply_tweet["id"], text, dry_run=dry_run)
            if reply_id or dry_run:
                if not dry_run and reply_id:
                    post_log = PostLog(
                        platform=PostPlatform.TWITTER,
                        post_type=PostType.ANALYSIS,
                        external_id=reply_id,
                        content_preview=text[:200],
                        metadata_={
                            "engagement_type": "reply",
                            "target_handle": handle,
                            "target_tweet_id": reply_tweet["id"],
                            "date": target_date,
                        },
                    )
                    db.add(post_log)
                    db.commit()
                summary["replies"] += 1

    return summary
