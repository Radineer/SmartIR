#!/usr/bin/env python3
"""Generate Iris VTuber 3D model via Meshy API: preview → refine → rig → download."""
import requests, time, os, sys, re, json
from datetime import datetime

API_KEY = os.environ.get("MESHY_API_KEY", "")
if not API_KEY:
    sys.exit("ERROR: MESHY_API_KEY not set")

BASE = "https://api.meshy.ai"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
SESSION = requests.Session()
SESSION.trust_env = False

OUTPUT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "meshy_output")
os.makedirs(OUTPUT_ROOT, exist_ok=True)

def create_task(endpoint, payload):
    resp = SESSION.post(f"{BASE}{endpoint}", headers=HEADERS, json=payload, timeout=30)
    if resp.status_code == 401:
        sys.exit("ERROR: Invalid API key (401)")
    if resp.status_code == 402:
        sys.exit("ERROR: Insufficient credits (402). Top up at https://www.meshy.ai/pricing")
    if resp.status_code == 429:
        sys.exit("ERROR: Rate limited (429). Wait and retry.")
    resp.raise_for_status()
    task_id = resp.json()["result"]
    print(f"TASK_CREATED: {task_id}", flush=True)
    return task_id

def poll_task(endpoint, task_id, timeout=600):
    elapsed = 0
    delay = 5
    max_delay = 30
    backoff = 1.5
    finalize_delay = 15
    poll_count = 0
    while elapsed < timeout:
        poll_count += 1
        resp = SESSION.get(f"{BASE}{endpoint}/{task_id}", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        task = resp.json()
        status = task["status"]
        progress = task.get("progress", 0)
        filled = int(progress / 5)
        bar = f"[{'█' * filled}{'░' * (20 - filled)}] {progress}%"
        print(f"  {bar} — {status} ({elapsed}s, poll #{poll_count})", flush=True)
        if status == "SUCCEEDED":
            return task
        if status in ("FAILED", "CANCELED"):
            msg = task.get("task_error", {}).get("message", "Unknown")
            sys.exit(f"TASK_{status}: {msg}")
        current_delay = finalize_delay if progress >= 95 else delay
        time.sleep(current_delay)
        elapsed += current_delay
        if progress < 95:
            delay = min(delay * backoff, max_delay)
    sys.exit(f"TIMEOUT after {timeout}s ({poll_count} polls)")

def download(url, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    print(f"Downloading {filepath}...", flush=True)
    resp = SESSION.get(url, timeout=300, stream=True)
    resp.raise_for_status()
    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"DOWNLOADED: {filepath} ({size_mb:.1f} MB)", flush=True)

# --- Project directory ---
PROMPT = "Anime VTuber girl, silver-white short bob haircut, bright blue eyes, wearing white lab coat over dark navy blouse, clean minimal style, full body standing pose, anime character design"

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
slug = re.sub(r'[^a-z0-9]+', '-', PROMPT.lower())[:30].strip('-')
project_dir = os.path.join(OUTPUT_ROOT, f"{timestamp}_iris-vtuber")
os.makedirs(project_dir, exist_ok=True)

print("=" * 60, flush=True)
print("STEP 1/3: Preview (mesh generation)", flush=True)
print("=" * 60, flush=True)

preview_id = create_task("/openapi/v2/text-to-3d", {
    "mode": "preview",
    "prompt": PROMPT,
    "ai_model": "latest",
    "pose_mode": "t-pose",  # Required for rigging later
})

task = poll_task("/openapi/v2/text-to-3d", preview_id)
download(task["model_urls"]["glb"], os.path.join(project_dir, "preview.glb"))
if task.get("thumbnail_url"):
    try:
        r = SESSION.get(task["thumbnail_url"], timeout=15)
        r.raise_for_status()
        open(os.path.join(project_dir, "thumbnail_preview.png"), "wb").write(r.content)
        print("Thumbnail saved.", flush=True)
    except Exception:
        pass

print("\n" + "=" * 60, flush=True)
print("STEP 2/3: Refine (PBR texturing)", flush=True)
print("=" * 60, flush=True)

refine_id = create_task("/openapi/v2/text-to-3d", {
    "mode": "refine",
    "preview_task_id": preview_id,
    "enable_pbr": True,
    "ai_model": "latest",
})

task = poll_task("/openapi/v2/text-to-3d", refine_id)
download(task["model_urls"]["glb"], os.path.join(project_dir, "refined.glb"))
if task.get("thumbnail_url"):
    try:
        r = SESSION.get(task["thumbnail_url"], timeout=15)
        r.raise_for_status()
        open(os.path.join(project_dir, "thumbnail_refined.png"), "wb").write(r.content)
    except Exception:
        pass

print("\n" + "=" * 60, flush=True)
print("STEP 3/3: Auto-Rigging (skeleton)", flush=True)
print("=" * 60, flush=True)

rig_id = create_task("/openapi/v1/rigging", {
    "input_task_id": refine_id,
    "height_meters": 1.6,
})

rig_task = poll_task("/openapi/v1/rigging", rig_id)
download(rig_task["result"]["rigged_character_glb_url"], os.path.join(project_dir, "rigged.glb"))

# Download basic animations
try:
    download(rig_task["result"]["basic_animations"]["walking_glb_url"],
             os.path.join(project_dir, "walking.glb"))
    download(rig_task["result"]["basic_animations"]["running_glb_url"],
             os.path.join(project_dir, "running.glb"))
except Exception as e:
    print(f"Animation download skipped: {e}", flush=True)

# Save metadata
metadata = {
    "character": "Iris",
    "prompt": PROMPT,
    "preview_task_id": preview_id,
    "refine_task_id": refine_id,
    "rig_task_id": rig_id,
    "created_at": datetime.now().isoformat(),
    "files": ["preview.glb", "refined.glb", "rigged.glb", "walking.glb", "running.glb"],
}
json.dump(metadata, open(os.path.join(project_dir, "metadata.json"), "w"), indent=2)

# Check remaining balance
bal = SESSION.get(f"{BASE}/openapi/v1/balance", headers=HEADERS, timeout=10)
balance = bal.json().get("balance", "?")

print("\n" + "=" * 60, flush=True)
print("COMPLETE!", flush=True)
print(f"  Project: {project_dir}", flush=True)
print(f"  Files: preview.glb, refined.glb, rigged.glb", flush=True)
print(f"  Remaining credits: {balance}", flush=True)
print("=" * 60, flush=True)
