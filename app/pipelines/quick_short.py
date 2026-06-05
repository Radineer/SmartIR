"""決算Flash - 15sec data-driven earnings shorts (no Hedra, no API cost)

Flow: earnings data -> script -> TTS -> Pillow frames -> FFmpeg -> MP4
Target: 3-5 shorts/day, fully automated
"""
import os, sys, math, tempfile, wave, struct, subprocess, json, logging
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)

FFMPEG = os.getenv("FFMPEG_PATH", "/opt/homebrew/Cellar/ffmpeg/8.1/bin/ffmpeg")
W, H, FPS = 1080, 1920, 30
OUTPUT_DIR = Path(os.getenv("SHORTS_OUTPUT_DIR", "./output/shorts"))

# ── Brand Colors ──
BG = (10, 10, 20)
BRAND = (255, 200, 0)       # Yellow - brand accent (lightning bolt)
GREEN = (0, 230, 118)       # Beat
RED = (255, 82, 82)         # Miss
WHITE = (255, 255, 255)
SILVER = (150, 160, 175)
GOLD = (255, 215, 0)
DARK_CARD = (18, 22, 38)
CARD_BORDER = (40, 44, 60)

_fc = {}
def font(size, bold=False):
    k = (size, bold)
    if k not in _fc:
        n = "ヒラギノ角ゴシック W6.ttc" if bold else "ヒラギノ角ゴシック W3.ttc"
        try: _fc[k] = ImageFont.truetype("/System/Library/Fonts/" + n, size)
        except: _fc[k] = ImageFont.load_default()
    return _fc[k]

def draw_rounded_rect(d, xy, fill, radius=16):
    d.rounded_rectangle(xy, radius=radius, fill=fill)

def text_centered(d, text, y, f, fill=WHITE):
    bb = d.textbbox((0,0), text, font=f)
    d.text(((W-(bb[2]-bb[0]))//2, y), text, font=f, fill=fill)

def text_right(d, text, x_right, y, f, fill=WHITE):
    bb = d.textbbox((0,0), text, font=f)
    d.text((x_right-(bb[2]-bb[0]), y), text, font=f, fill=fill)

def get_audio_amps(wav_path, fps=30):
    with wave.open(wav_path, "rb") as wf:
        nc, sw, fr = wf.getnchannels(), wf.getsampwidth(), wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if sw == 2:
        samples = struct.unpack("<%dh" % (len(raw)//2), raw)
    else:
        samples = [0]*(len(raw)//sw)
    spf = max(1, fr//fps)
    amps = []
    for i in range(0, len(samples), spf*nc):
        c = samples[i:i+spf*nc]
        amps.append(min(math.sqrt(sum(s*s for s in c)/max(len(c),1))/32768*4, 1.0) if c else 0)
    return amps


def _draw_brand_header(d):
    """Common brand header: 決算Flash logo + top accent bar"""
    # Top accent bar
    d.rectangle([(0, 0), (W, 4)], fill=BRAND)
    # Brand logo: yellow bar + text
    draw_rounded_rect(d, (30, 14, 44, 50), fill=BRAND, radius=4)
    d.text((52, 16), "決算", font=font(26, True), fill=WHITE)
    d.text((128, 16), "Flash", font=font(26, True), fill=BRAND)


def render_hook_frame(company, ticker, beat_miss="neutral", period=""):
    """Frame 1: Big company name + BEAT/MISS badge"""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    _draw_brand_header(d)

    # Company name (large, center)
    cy = H // 2 - 200
    text_centered(d, company, cy, font(72, True), WHITE)
    # Ticker
    text_centered(d, "(" + ticker + ")", cy + 90, font(44), SILVER)

    # Beat / Miss badge (huge, center)
    badge_y = cy + 180
    if beat_miss == "beat":
        badge_color = GREEN
        badge_text = "BEAT"
        badge_icon = "▲"
    elif beat_miss == "miss":
        badge_color = RED
        badge_text = "MISS"
        badge_icon = "▼"
    else:
        badge_color = BRAND
        badge_text = "速報"
        badge_icon = "◆"

    # Badge background
    bw, bh = 420, 120
    bx = (W - bw) // 2
    draw_rounded_rect(d, (bx, badge_y, bx + bw, badge_y + bh), fill=badge_color, radius=24)
    # Badge text
    f_badge = font(64, True)
    bb = d.textbbox((0,0), badge_icon + " " + badge_text, font=f_badge)
    tw = bb[2] - bb[0]
    d.text(((W - tw) // 2, badge_y + 22), badge_icon + " " + badge_text, font=f_badge, fill=WHITE if beat_miss != "neutral" else BG)

    # Period below badge
    if period:
        text_centered(d, period, badge_y + bh + 30, font(36), SILVER)

    # Bottom accent
    d.rectangle([(0, H - 4), (W, H)], fill=BRAND)

    return img


def render_data_frame(title, metrics, subtitle="", progress=0.0, highlight_idx=-1, beat_miss="neutral"):
    """Data-heavy frame with metrics cards"""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    _draw_brand_header(d)

    # Title bar
    d.rectangle([(0, 60), (W, 145)], fill=(15, 15, 32))
    text_centered(d, title, 78, font(42, True), WHITE)
    # Beat/Miss indicator dot in title bar
    if beat_miss == "beat":
        d.ellipse([(W - 60, 85), (W - 40, 105)], fill=GREEN)
    elif beat_miss == "miss":
        d.ellipse([(W - 60, 85), (W - 40, 105)], fill=RED)
    d.rectangle([(0, 143), (W, 145)], fill=BRAND)

    # Metrics cards
    y = 170
    for i, m in enumerate(metrics):
        card_h = 140
        is_hl = (i == highlight_idx)
        bg_c = (25, 30, 50) if is_hl else DARK_CARD
        border_c = BRAND if is_hl else CARD_BORDER

        draw_rounded_rect(d, (30, y, W - 30, y + card_h), fill=bg_c, radius=16)
        # Left accent bar
        bar_color = m.get("indicator", border_c)
        d.rectangle([(30, y + 10), (38, y + card_h - 10)], fill=bar_color)

        # Label
        d.text((55, y + 15), m["label"], font=font(24), fill=SILVER)

        # Value (BIG)
        val_color = m.get("color", WHITE)
        d.text((55, y + 48), m["value"], font=font(56, True), fill=val_color)

        # Change (right side)
        if m.get("change"):
            c = GREEN if "+" in m["change"] or "▲" in m["change"] or "Beat" in m["change"] else RED if "-" in m["change"] or "▼" in m["change"] or "Miss" in m["change"] else SILVER
            text_right(d, m["change"], W - 50, y + 55, font(28, True), c)

        # Sub info
        if m.get("sub"):
            d.text((55, y + card_h - 30), m["sub"], font=font(16), fill=SILVER)

        y += card_h + 12

    # Subtitle bar (narration text)
    if subtitle:
        sy = H - 240
        sh = 80
        draw_rounded_rect(d, (25, sy, W - 25, sy + sh), fill=(0, 0, 0), radius=14)
        d.rectangle([(25, sy + 8), (33, sy + sh - 8)], fill=BRAND)

        f_sub = font(28, True)
        mx = 24
        lines = [subtitle[i:i+mx] for i in range(0, len(subtitle), mx)]
        ty = sy + (sh - len(lines) * 36) // 2
        for line in lines:
            bb = d.textbbox((0,0), line, font=f_sub)
            d.text(((W - (bb[2]-bb[0])) // 2, ty), line, font=f_sub, fill=WHITE)
            ty += 36

    # CTA
    cta_y = H - 130
    draw_rounded_rect(d, (100, cta_y, W - 100, cta_y + 52), fill=BRAND, radius=26)
    text_centered(d, "@kessan_flash フォローで毎日届く", cta_y + 12, font(24, True), BG)

    # Progress bar
    d.rectangle([(0, H - 4), (int(W * progress), H)], fill=BRAND)

    # Disclaimer
    text_centered(d, "※投資判断はご自身の責任で", H - 25, font(12), (60, 60, 80))

    return img


def generate_quick_short(
    company_name,
    ticker,
    hook,
    metrics,
    script_lines,
    output_path=None,
    beat_miss="neutral",
    period="",
):
    """
    Generate a 15-second data-driven short video.

    Args:
        company_name: e.g. "トヨタ自動車"
        ticker: e.g. "7203"
        hook: Big text for first 2 seconds (used in title, not displayed as raw text anymore)
        metrics: [{label, value, change, color?, sub?, indicator?}, ...]
        script_lines: Narration lines (TTS)
        output_path: Output MP4 path
        beat_miss: "beat" / "miss" / "neutral"
        period: e.g. "2026年3月期 3Q"
    """
    tts = TTSService()
    title = company_name + "(" + ticker + ")"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(OUTPUT_DIR / ("short_" + ticker + "_" + ts + ".mp4"))

    with tempfile.TemporaryDirectory(prefix="qshort_") as tmp:
        # TTS
        segments = []
        for i, line in enumerate(script_lines):
            segments.append({"id": "s%02d" % i, "text": line})
        segments = tts.synthesize_segments(segments, os.path.join(tmp, "audio"))

        # Concat audio
        all_raw = b""
        params = None
        for seg in segments:
            with wave.open(seg["audio_path"], "rb") as wf:
                if params is None:
                    params = wf.getparams()
                all_raw += wf.readframes(wf.getnframes())

        audio_path = os.path.join(tmp, "full.wav")
        with wave.open(audio_path, "wb") as out:
            out.setparams(params)
            out.writeframes(all_raw)

        total_dur = sum(s["duration"] for s in segments)
        logger.info("Audio: %.1fs" % total_dur)

        # Timeline
        timeline = []
        t = 0.0
        for seg in segments:
            timeline.append({"start": t, "end": t + seg["duration"], "text": seg["text"]})
            t += seg["duration"]

        # Render frames
        frames_dir = os.path.join(tmp, "frames")
        os.makedirs(frames_dir)
        total_frames = int(total_dur * FPS)

        hook_end = timeline[0]["end"] if timeline else 2.0

        logger.info("Rendering %d frames..." % total_frames)
        last_sub = None
        last_frame = None

        for fi in range(total_frames):
            t = fi / FPS
            progress = t / total_dur

            # Current subtitle
            sub = ""
            for tl in timeline:
                if tl["start"] <= t < tl["end"]:
                    sub = tl["text"]
                    break

            # Highlight index
            data_progress = (t - hook_end) / (total_dur - hook_end) if t > hook_end else 0
            highlight_idx = min(int(data_progress * len(metrics)), len(metrics) - 1) if data_progress > 0 else -1

            if sub != last_sub or fi % 10 == 0:
                if t < hook_end:
                    frame = render_hook_frame(company_name, ticker, beat_miss, period)
                else:
                    frame = render_data_frame(
                        title=title,
                        metrics=metrics,
                        subtitle=sub,
                        progress=progress,
                        highlight_idx=highlight_idx,
                        beat_miss=beat_miss,
                    )
                last_sub = sub
                last_frame = frame

            last_frame.save(os.path.join(frames_dir, "f_%05d.png" % fi))

        # FFmpeg
        logger.info("Encoding...")
        cmd = [
            FFMPEG, "-y",
            "-framerate", str(FPS),
            "-i", os.path.join(frames_dir, "f_%05d.png"),
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-shortest", output_path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError("FFmpeg failed: " + r.stderr[-300:])

        mb = os.path.getsize(output_path) / 1024 / 1024
        logger.info("Video: %s (%.1fMB, %.1fs)" % (output_path, mb, total_dur))

        bm_tag = ""
        if beat_miss == "beat":
            bm_tag = " 予想超え"
        elif beat_miss == "miss":
            bm_tag = " 予想下回る"

        return {
            "video_path": output_path,
            "duration": total_dur,
            "title": "【決算Flash】%s(%s)%s%s #Shorts" % (company_name, ticker, bm_tag, " " + hook if hook else ""),
            "description": (
                company_name + "の最新決算を15秒で解説。\n\n"
                + "\n".join("・%s: %s %s" % (m["label"], m["value"], m.get("change", "")) for m in metrics)
                + "\n\n#決算Flash #決算 #株式投資 #日本株"
            ),
        }


# ── CLI Test ──
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    result = generate_quick_short(
        company_name="トヨタ自動車",
        ticker="7203",
        hook="営業利益 過去最高",
        beat_miss="beat",
        period="2026年3月期 3Q",
        metrics=[
            {"label": "売上高", "value": "45兆円", "change": "+12% YoY", "indicator": GREEN, "sub": "前年比4.8兆円増"},
            {"label": "営業利益", "value": "5.3兆円", "change": "▲ Beat", "color": GREEN, "indicator": GREEN, "sub": "営業利益率11.8%"},
            {"label": "通期見通し", "value": "上方修正", "change": "▲ 予想超", "color": BRAND, "indicator": GREEN, "sub": "2回目の上方修正"},
            {"label": "配当予想", "value": "90円/株", "change": "+15円増配", "color": GOLD, "indicator": GREEN, "sub": "配当性向30%"},
        ],
        script_lines=[
            "速報。トヨタ、営業利益が過去最高を更新。",
            "売上高45兆円、前年比12パーセント増。",
            "営業利益5.3兆円。北米好調と円安が貢献。",
            "通期見通しも上方修正。決算フラッシュ、フォローで毎日届く。",
        ],
        output_path="/tmp/smartir_shorts/quick_test.mp4",
    )

    print("\nTitle: " + result["title"])
    print("Video: " + result["video_path"])
    print("Duration: %.1fs" % result["duration"])
