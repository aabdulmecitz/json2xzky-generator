#!/usr/bin/env python3
"""
main_factory.py — Autonomous Video Orchestrator Pipeline
=========================================================
Converts a raw scenario.txt → structured scenario.json → headless Playwright
recording → FFmpeg muxed final_video.mp4
 
Pipeline:
  1. The Brain     — Ollama local LLM parses script.txt → scenario.json
  2. The Fetcher   — Scrapes MyInstants for missing meme sounds
  3. The Actor     — Playwright records a silent 1080×1920 video
  4. The Muxer     — FFmpeg layers audio at exact timestamps
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR   = PROJECT_ROOT / "assets"
SOUNDS_DIR   = ASSETS_DIR / "sounds" / "mp3"
WEB_DIR      = PROJECT_ROOT / "web_player"
OUTPUT_DIR   = PROJECT_ROOT / "output"
ZOOMS_DIR    = OUTPUT_DIR / "zooms"

SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ZOOMS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
USER_AGENT   = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. THE BRAIN — Ollama Integration
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a Discord scenario JSON generator for a video simulator.
You receive a plain‑text chat script and MUST output a **single valid JSON array** — nothing else.

RULES:
• Each element is an object with these fields:
  - "id"               (int, auto‑incrementing from 1)
  - "user_id"          (str, the speaker's display name)
  - "message_content"  (str, the message text — can be empty for join/leave)
  - "action"           (one of: "join", "leave", "typing", "message", "reply",
                         "send_attachment", "send_voice_note", "add_reaction",
                         "edit_message", "delete_message", "open_sidebar",
                         "close_sidebar", "push_notification", "incoming_call",
                         "open_profile", "system_message")
  - "reply_to_id"      (int|null, the id of the message being replied to)
  - "has_ping"         (bool, true if the message @‑mentions someone)
  - "pause_after"      (float, seconds to wait after this event)
  - "sound"            (str|null, local sound file stem e.g. "vineboom")
  - "sound_query"      (str|null, descriptive query to fetch from the internet
                         if the sound file is not found locally, e.g. "vine thud")
  - "zoom"             (bool, true if this message should trigger a
                         'Beluga Camera' dramatic zoom‑in effect during recording.
                         Use sparingly — only for comedic punchlines or dramatic moments.)

• For each message, ALWAYS emit a "typing" entry BEFORE the "message" entry
  so the simulator shows the typing indicator.
• Use "has_ping": true when the message contains @SomeUser.
• Use "zoom": true on the funniest or most dramatic messages (about 1 in 5).

Output the JSON array only. No markdown fences, no commentary."""


def parse_text_to_json(text_file: str, output_json: str | None = None) -> list:
    """
    Read a scenario .txt file and ask Ollama to produce structured JSON.
    Falls back to the legacy regex parser if Ollama is unreachable.
    """
    text_path = Path(text_file)
    if not text_path.exists():
        print(f"[BRAIN] ❌ File not found: {text_path}")
        sys.exit(1)

    raw_text = text_path.read_text(encoding="utf-8")
    print(f"[BRAIN] 📖 Read {len(raw_text)} chars from {text_path.name}")

    try:
        import ollama
        print(f"[BRAIN] 🧠 Asking {OLLAMA_MODEL} to parse the script...")
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": raw_text},
            ],
            options={"temperature": 0.1},
        )
        content = response["message"]["content"]

        # Strip markdown fences if the model added them anyway
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"```\s*$", "", content, flags=re.MULTILINE)

        scenario = json.loads(content.strip())
        print(f"[BRAIN] ✅ Parsed {len(scenario)} entries via Ollama")

    except ImportError:
        print("[BRAIN] ⚠️  `ollama` library not installed — using legacy parser")
        scenario = _legacy_parse(raw_text)
    except Exception as e:
        print(f"[BRAIN] ⚠️  Ollama error ({e}) — falling back to legacy parser")
        scenario = _legacy_parse(raw_text)

    scenario = _apply_sequential_reveal_groups(scenario)

    # Write output
    if output_json is None:
        output_json = str(text_path.with_suffix(".json"))
    Path(output_json).write_text(json.dumps(scenario, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[BRAIN] 💾 Saved → {output_json}")
    return scenario


def _legacy_parse(raw_text: str) -> list:
    """
    Deterministic regex parser that handles the existing .txt format:
      WELCOME User$^delay#!sound
      User:
      message$^delay#!sound
    """
    lines = [l.rstrip() for l in raw_text.splitlines() if l.strip()]
    entries: list[dict] = []
    current_user = None
    msg_id = 0

    for line in lines:
        # WELCOME line  →  join event
        m = re.match(r"WELCOME\s+(\S+)\$\^([\d.]+)#!(\w+)", line)
        if m:
            msg_id += 1
            entries.append({
                "id": msg_id,
                "user_id": m.group(1),
                "message_content": "",
                "action": "join",
                "reply_to_id": None,
                "has_ping": False,
                "pause_after": float(m.group(2)),
                "sound": m.group(3),
                "sound_query": None,
                "zoom": False,
            })
            current_user = None
            continue

        # User header (e.g.  "Billy:")
        m = re.match(r"^(\w+):\s*$", line)
        if m:
            current_user = m.group(1)
            continue

        # Message line
        m = re.match(r"^(.+)\$\^([\d.]+)#!(\w+)\s*$", line)
        if m and current_user:
            text    = m.group(1).strip()
            delay   = float(m.group(2))
            sound   = m.group(3)
            has_ping = bool(re.search(r"@\w+", text))

            # Typing event first
            msg_id += 1
            entries.append({
                "id": msg_id,
                "user_id": current_user,
                "message_content": text,
                "action": "typing",
                "reply_to_id": None,
                "has_ping": False,
                "pause_after": 0.0,
                "sound": None,
                "sound_query": None,
                "zoom": False,
            })

            # Then the actual message
            # Auto-detect dramatic moments for zoom
            is_dramatic = sound in ("vineboom", "explosion", "scary", "hehascome", "error")
            msg_id += 1
            entries.append({
                "id": msg_id,
                "user_id": current_user,
                "message_content": text,
                "action": "message",
                "reply_to_id": None,
                "has_ping": has_ping,
                "pause_after": delay,
                "sound": sound,
                "sound_query": None,
                "zoom": is_dramatic,
            })
            continue

    print(f"[BRAIN] ✅ Legacy parser produced {len(entries)} entries")
    return entries


def _apply_sequential_reveal_groups(scenario: list) -> list:
    """
    Scans the scenario for consecutive 'message' actions by the same user.
    If 3 or more are found consecutively (ignoring typing/delays in between),
    group them into a 'sequential_reveal' crop_mode.
    """
    current_user = None
    group_indices = []
    group_counter = 1
    
    def process_group(indices, group_id):
        if len(indices) >= 3:
            for i in indices:
                scenario[i]["crop_mode"] = "sequential_reveal"
                scenario[i]["reveal_group_id"] = group_id
    
    for i, entry in enumerate(scenario):
        if entry.get("action") in ["message", "send_message", "reply", "send_attachment"]:
            user = entry.get("user_id")
            if user == current_user:
                group_indices.append(i)
            else:
                if group_indices:
                    process_group(group_indices, group_counter)
                    if len(group_indices) >= 3:
                        group_counter += 1
                current_user = user
                group_indices = [i]
                
    if group_indices:
        process_group(group_indices, group_counter)
        
    return scenario

# ═══════════════════════════════════════════════════════════════════════════
# 2. THE FETCHER — MyInstants Dynamic Audio Scraper
# ═══════════════════════════════════════════════════════════════════════════

def resolve_audio_assets(scenario: list) -> list:
    """
    Scan every entry for 'sound' or 'sound_query' fields.
    If the mp3 doesn't exist locally, attempt to download it from MyInstants.
    Mutates the list in‑place and returns it.
    """
    import requests
    from bs4 import BeautifulSoup

    queries_to_resolve: set[str] = set()

    for entry in scenario:
        for key in ("sound", "sound_query"):
            name = entry.get(key)
            if name and not (SOUNDS_DIR / f"{name}.mp3").exists():
                queries_to_resolve.add(name)

    if not queries_to_resolve:
        print("[FETCHER] ✅ All audio assets exist locally")
        return scenario

    print(f"[FETCHER] 🔎 Need to fetch {len(queries_to_resolve)} sound(s): {queries_to_resolve}")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for query in queries_to_resolve:
        if _download_from_myinstants(session, query):
            print(f"[FETCHER] ✅ Downloaded: {query}.mp3")
        else:
            print(f"[FETCHER] ⚠️  Could not find \"{query}\" on MyInstants — skipping")

    # Normalise: if sound_query was used, copy its value into the sound field
    for entry in scenario:
        sq = entry.get("sound_query")
        if sq:
            entry["sound"] = sq.replace(" ", "_")
            entry["sound_query"] = None

    return scenario


def _download_from_myinstants(session, query: str) -> bool:
    """
    Search MyInstants, parse the first result's mp3 URL, download it.
    """
    from bs4 import BeautifulSoup

    search_url = f"https://www.myinstants.com/en/search/?name={urllib.parse.quote_plus(query)}"
    try:
        resp = session.get(search_url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[FETCHER] ❌ HTTP error for query \"{query}\": {e}")
        return False

    soup = BeautifulSoup(resp.text, "html.parser")

    # MyInstants stores the mp3 URL inside <div class="small-button"> onclick attrs
    # or inside <a> tags with /media/sounds/*.mp3
    mp3_url = None

    # Strategy 1: look in onclick attributes of play buttons
    for btn in soup.select(".small-button"):
        onclick = btn.get("onclick", "")
        match = re.search(r"play\('(.*?\.mp3)'", onclick)
        if match:
            mp3_url = match.group(1)
            break

    # Strategy 2: look for direct links to .mp3
    if not mp3_url:
        for a_tag in soup.find_all("a", href=True):
            if ".mp3" in a_tag["href"]:
                mp3_url = a_tag["href"]
                break

    # Strategy 3: look in any element that has a data-url or data-src with .mp3
    if not mp3_url:
        for el in soup.find_all(attrs={"data-url": True}):
            if ".mp3" in el["data-url"]:
                mp3_url = el["data-url"]
                break

    if not mp3_url:
        return False

    # Resolve relative URLs
    if mp3_url.startswith("//"):
        mp3_url = "https:" + mp3_url
    elif mp3_url.startswith("/"):
        mp3_url = "https://www.myinstants.com" + mp3_url

    # Download the mp3
    try:
        audio_resp = session.get(mp3_url, timeout=15)
        audio_resp.raise_for_status()
        safe_name = query.replace(" ", "_")
        out_path = SOUNDS_DIR / f"{safe_name}.mp3"
        out_path.write_bytes(audio_resp.content)
        return True
    except Exception as e:
        print(f"[FETCHER] ❌ Download failed for \"{query}\": {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# 3. THE ACTOR — Playwright Headless Recorder
# ═══════════════════════════════════════════════════════════════════════════

def record_simulation(json_file: str) -> tuple[str, list[dict], list[dict]]:
    """
    Launch a headless browser at 1080×1920, serve the web_player,
    inject the scenario JSON, record video, collect audio timeline
    and camera zoom cues.
    Returns (raw_video_path, audio_timeline, camera_cues).
    """
    from playwright.sync_api import sync_playwright
    import http.server
    import threading

    json_path = Path(json_file).resolve()
    raw_video_dir = OUTPUT_DIR / "raw_recordings"
    raw_video_dir.mkdir(exist_ok=True)

    audio_timeline: list[dict] = []
    camera_cues: list[dict] = []
    reveal_cues: list[dict] = []

    # Start a simple HTTP server for the web_player directory
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)
        def log_message(self, *a):
            pass  # Suppress noisy logs

    server = http.server.HTTPServer(("127.0.0.1", 0), QuietHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[ACTOR] 🌐 Local server on http://127.0.0.1:{port}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 432, "height": 768},
            device_scale_factor=2.5,
            record_video_dir=str(raw_video_dir),
            record_video_size={"width": 1080, "height": 1920},
        )
        page = context.new_page()

        # Collect audio events and zoom cues from console
        def on_console(msg):
            text = msg.text
            if text == "SIMULATION_COMPLETE":
                return
            try:
                data = json.loads(text)
                if data.get("type") == "AUDIO_EVENT":
                    audio_timeline.append({
                        "file": str(ASSETS_DIR.parent / data["file"]),
                        "timestamp": data["timestamp"],
                    })
                elif data.get("type") == "ZOOM_CUE":
                    camera_cues.append(data)
                elif data.get("type") == "REVEAL_TIMESTAMP":
                    reveal_cues.append(data)
            except (json.JSONDecodeError, KeyError):
                pass

        page.on("console", on_console)

        # Navigate
        url = f"http://127.0.0.1:{port}/web_player/index.html"
        print(f"[ACTOR] 🎬 Navigating to {url}")
        page.goto(url, wait_until="networkidle")

        # Read and inject the scenario JSON directly
        scenario_data = json_path.read_text(encoding="utf-8")
        page.evaluate(f"""
            scenarioEntries = {scenario_data};
            document.getElementById('start-btn').disabled = false;
            document.getElementById('instant-btn').disabled = false;
        """)

        # Hide the overlay and start the simulation (with audio context)
        page.evaluate("""
            (async () => {{
                window.AudioContext = window.AudioContext || window.webkitAudioContext;
                audioCtx = new AudioContext();
                await preloadCoreSounds();
                document.getElementById('start-overlay').classList.add('hidden');
                document.body.classList.add('recording-mode');
                runSimulation();
            }})();
        """)

        # Wait for SIMULATION_COMPLETE
        print("[ACTOR] ⏳ Waiting for simulation to complete...")
        page.wait_for_function(
            """() => {
                return window.__simulationDone === true;
            }""",
            timeout=300_000,  # 5 min max
        )

        # Give some extra time for the last animation to finish
        page.wait_for_timeout(2000)

        # ── Beluga Camera: take element screenshots for zoom cues ──────
        if camera_cues:
            print(f"[ACTOR] 📸 Capturing {len(camera_cues)} zoom screenshots...")
            for cue in camera_cues:
                msg_id = cue["msg_id"]
                locator = page.locator(f"#msg_{msg_id}")
                if locator.count() > 0:
                    screenshot_path = ZOOMS_DIR / f"msg_{msg_id}.png"
                    locator.screenshot(path=str(screenshot_path))
                    cue["screenshot"] = str(screenshot_path)
                    print(f"[ACTOR]   📷 msg_{msg_id} → {screenshot_path.name}")
                else:
                    print(f"[ACTOR]   ⚠️  msg_{msg_id} not found in DOM")

        # ── Pass 2: Sequential Reveal High-Res Screenshots ──────
        if reveal_cues:
            print(f"[ACTOR] 📸 Capturing Sequential Reveals (Pass 2 - Scale 3.0)...")
            
            groups = {}
            for cue in reveal_cues:
                groups.setdefault(cue["group_id"], []).append(cue)
                
            context2 = browser.new_context(
                viewport={"width": 432, "height": 768},
                device_scale_factor=4.0
            )
            page2 = context2.new_page()
            page2.goto(url, wait_until="networkidle")
            
            page2.evaluate(f"""
                scenarioEntries = {scenario_data};
                const overlay = document.getElementById('start-overlay');
                if (overlay) overlay.remove();
                document.body.classList.add('recording-mode');
                document.body.classList.add('instant-mode');
                isInstant = true;
                runSimulation();
            """)
            page2.wait_for_timeout(1000) 
            
            # Wait for any avatars/images to finish loading so they don't clip out
            page2.evaluate("""
                () => new Promise(resolve => {
                    if (document.images.length === 0) resolve();
                    let loaded = 0;
                    for (let img of document.images) {
                        if (img.complete) loaded++;
                        else img.addEventListener('load', () => { loaded++; if (loaded === document.images.length) resolve(); });
                        img.addEventListener('error', () => { loaded++; if (loaded === document.images.length) resolve(); });
                    }
                    if (loaded >= document.images.length) resolve();
                })
            """)
            
            for gid, group_cues in groups.items():
                msg_ids = [c["msg_id"] for c in group_cues]
                for step_idx in range(len(msg_ids)):
                    page2.evaluate(f"""
                        var hideIds = {msg_ids};
                        for (var i=0; i<hideIds.length; i++) {{
                            var el = document.getElementById('msg_' + hideIds[i]);
                            if (el) {{
                                el.style.display = (i <= {step_idx}) ? 'flex' : 'none';
                            }}
                        }}
                    """)
                    page2.wait_for_timeout(100) 
                    
                    bbox = page2.evaluate(f"""
                        (function() {{
                            var ids = {msg_ids};
                            var minX = 99999, minY = 99999, maxX = 0, maxY = 0;
                            var found = false;
                            for (var i=0; i<ids.length; i++) {{
                                if (i > {step_idx}) continue;
                                var el = document.getElementById('msg_' + ids[i]);
                                if (el) {{
                                    found = true;
                                    var r = el.getBoundingClientRect();
                                    if (r.x < minX) minX = r.x;
                                    if (r.y < minY) minY = r.y;
                                    if (r.x+r.width > maxX) maxX = r.x+r.width;
                                    if (r.y+r.height > maxY) maxY = r.y+r.height;
                                }}
                            }}
                            if (!found) return null;
                            return {{x: minX, y: minY, width: maxX-minX, height: maxY-minY}};
                        }})()
                    """)
                    
                    if bbox:
                        pad = 20
                        clip = {
                            "x": max(0, bbox["x"] - pad),
                            "y": max(0, bbox["y"] - pad),
                            "width": bbox["width"] + pad*2,
                            "height": bbox["height"] + pad*2
                        }
                        
                        shot_name = f"reveal_g{gid}_step{step_idx}.png"
                        shot_path = ZOOMS_DIR / shot_name
                        page2.screenshot(path=str(shot_path), clip=clip)
                        group_cues[step_idx]["screenshot"] = str(shot_path)
                        print(f"[ACTOR]   📷 reveal_g{gid}_step{step_idx} → {shot_name}")
            
            context2.close()

        # Close to save the video
        page.close()
        context.close()
        browser.close()

    server.shutdown()

    # Find the recorded video webm/mp4
    video_files = sorted(raw_video_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not video_files:
        print("[ACTOR] ❌ No video file found after recording!")
        sys.exit(1)

    raw_video = video_files[0]
    final_raw = OUTPUT_DIR / "raw_video.mp4"

    # Convert to mp4 if needed (Playwright records as webm)
    if raw_video.suffix == ".webm":
        print("[ACTOR] 🔄 Converting webm → mp4...")
        subprocess.run([
            "ffmpeg", "-y", "-i", str(raw_video),
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            str(final_raw),
        ], capture_output=True)
    else:
        import shutil
        shutil.copy2(str(raw_video), str(final_raw))

    # Save audio timeline
    timeline_path = OUTPUT_DIR / "audio_timeline.json"
    timeline_path.write_text(json.dumps(audio_timeline, indent=2), encoding="utf-8")
    print(f"[ACTOR] 💾 Audio timeline: {timeline_path}  ({len(audio_timeline)} events)")

    # Save camera cues
    cues_path = OUTPUT_DIR / "camera_cues.json"
    cues_path.write_text(json.dumps(camera_cues, indent=2), encoding="utf-8")
    print(f"[ACTOR] 📐 Camera cues: {cues_path}  ({len(camera_cues)} zoom cues)")
    
    # Save reveal cues
    reveal_path = OUTPUT_DIR / "reveal_cues.json"
    reveal_path.write_text(json.dumps(reveal_cues, indent=2), encoding="utf-8")
    print(f"[ACTOR] 🌠 Reveal cues: {reveal_path}  ({len(reveal_cues)} sequential reveal steps)")
    
    print(f"[ACTOR] 🎥 Raw video: {final_raw}")

    return str(final_raw), audio_timeline, camera_cues, reveal_cues


# ═══════════════════════════════════════════════════════════════════════════
# 4. THE MUXER — FFmpeg Audio Layering
# ═══════════════════════════════════════════════════════════════════════════

def mux_audio_video(
    raw_video: str = None,
    audio_timeline: list[dict] = None,
    camera_cues: list[dict] = None,
    reveal_cues: list[dict] = None,
) -> str:
    """
    Layer all audio events at their exact timestamps over the silent video.
    Apply Beluga Camera zoom crops when camera_cues exist.
    Produces output/final_video.mp4.
    """
    if raw_video is None:
        raw_video = str(OUTPUT_DIR / "raw_video.mp4")
    if audio_timeline is None:
        tl_path = OUTPUT_DIR / "audio_timeline.json"
        audio_timeline = json.loads(tl_path.read_text(encoding="utf-8"))
    if camera_cues is None:
        cues_path = OUTPUT_DIR / "camera_cues.json"
        if cues_path.exists():
            camera_cues = json.loads(cues_path.read_text(encoding="utf-8"))
        else:
            camera_cues = []

    if not audio_timeline and not camera_cues:
        print("[MUXER] ⚠️  No audio events or zoom cues — copying raw video as final")
        import shutil
        final = str(OUTPUT_DIR / "final_video.mp4")
        shutil.copy2(raw_video, final)
        return final

    # ── Step A: Apply zoom crops if we have camera cues ─────────────────
    zoomed_video = raw_video
    if camera_cues:
        print(f"[MUXER] 🎯 Applying {len(camera_cues)} Beluga Camera zoom cuts...")
        zoomed_video = _apply_zoom_crops(raw_video, camera_cues)
        
    # ── Step A2: Apply sequential reveals ────────────────────────────────
    if reveal_cues:
        # Check if the screenshots exist
        valid_reveals = [c for c in reveal_cues if "screenshot" in c and Path(c["screenshot"]).exists()]
        if valid_reveals:
            print(f"[MUXER] 🎯 Applying {len(valid_reveals)} Sequential Reveal edits...")
            zoomed_video = _apply_sequential_reveals(zoomed_video, valid_reveals)

    # ── Step B: Layer audio ─────────────────────────────────────────────
    # De-duplicate audio events
    seen = set()
    unique_timeline = []
    for ev in audio_timeline:
        key = (ev["file"], round(ev["timestamp"], 2))
        if key not in seen:
            seen.add(key)
            unique_timeline.append(ev)

    # Filter out audio files that don't exist
    valid_events = []
    for ev in unique_timeline:
        if Path(ev["file"]).exists():
            valid_events.append(ev)
        else:
            print(f"[MUXER] ⚠️  Missing audio file: {ev['file']} — skipped")

    if not valid_events:
        if zoomed_video != raw_video:
            # We have zoomed video but no audio — just copy it
            import shutil
            final = str(OUTPUT_DIR / "final_video.mp4")
            shutil.copy2(zoomed_video, final)
            return final
        print("[MUXER] ⚠️  No valid audio files — copying raw video as final")
        import shutil
        final = str(OUTPUT_DIR / "final_video.mp4")
        shutil.copy2(raw_video, final)
        return final

    # Add sounds for camera zoom cues
    vine_thud = str(SOUNDS_DIR / "vine_thud.mp3")
    fallback_ping = str(SOUNDS_DIR / "discord_ping.mp3")
    
    if Path(vine_thud).exists() and camera_cues:
        for cue in camera_cues:
            valid_events.append({
                "file": vine_thud,
                "timestamp": cue["timestamp"],
            })
        print(f"[MUXER] 💥 Added vine_thud at {len(camera_cues)} zoom timestamps")

    # Add massive punchy sound for sequential reveal steps
    sound_to_use = vine_thud if Path(vine_thud).exists() else fallback_ping
    if Path(sound_to_use).exists() and reveal_cues:
        for cue in reveal_cues:
            valid_events.append({
                "file": sound_to_use,
                "timestamp": cue["timestamp"],
            })
        print(f"[MUXER] 🌠 Added reveal sound at {len(reveal_cues)} timestamps")

    print(f"[MUXER] 🎵 Layering {len(valid_events)} audio events onto video...")

    # Build the FFmpeg command using the complex filtergraph
    cmd = ["ffmpeg", "-y", "-i", zoomed_video]

    for ev in valid_events:
        cmd.extend(["-i", ev["file"]])

    # Build the filter complex
    filter_parts = []
    for i, ev in enumerate(valid_events):
        delay_ms = int(ev["timestamp"] * 1000)
        filter_parts.append(f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

    # Mix all delayed audio streams together
    mix_inputs = "".join(f"[a{i}]" for i in range(len(valid_events)))
    filter_parts.append(f"{mix_inputs}amix=inputs={len(valid_events)}:dropout_transition=0[aout]")

    filter_complex = ";".join(filter_parts)

    final_path = str(OUTPUT_DIR / "final_video.mp4")
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        final_path,
    ])

    print(f"[MUXER] 🔧 Running FFmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[MUXER] ❌ FFmpeg error:\n{result.stderr[-500:]}")
        import shutil
        shutil.copy2(zoomed_video, final_path)
        print("[MUXER] ⚠️  Copied video as fallback")
    else:
        print(f"[MUXER] ✅ Final video → {final_path}")

    return final_path


def _apply_zoom_crops(raw_video: str, camera_cues: list[dict]) -> str:
    """
    Apply Beluga-style zoom edits to the video using FFmpeg.
    For each zoom cue, we crop+scale the bounding box region to fill
    the 1080x1920 frame for 1.5 seconds, then cut back to the full view.
    """
    ZOOM_DURATION = 1.5  # seconds each zoom lasts
    
    # Build a complex filtergraph that overlays zoomed segments
    # Strategy: Use FFmpeg's crop and scale to zoom into the bbox,
    # then use overlay with enable='between(t,start,end)'
    
    filter_parts = []
    overlay_chain = "[0:v]"
    
    for i, cue in enumerate(camera_cues):
        bbox = cue["bbox"]
        t_start = cue["timestamp"]
        t_end = t_start + ZOOM_DURATION
        
        # Crop coordinates (clamped to video bounds)
        # Muxer extracts from physical pixels, so scale from CSS
        scale_factor = 2.5
        cx = max(0, bbox["x"] * scale_factor)
        cy = max(0, bbox["y"] * scale_factor)
        cw = max(100, bbox["width"] * scale_factor)
        ch = max(100, bbox["height"] * scale_factor)
        
        # Add padding around the message for cinematic feel
        pad = 40 * scale_factor
        cx = max(0, cx - pad)
        cy = max(0, cy - pad)
        cw = cw + pad * 2
        ch = ch + pad * 2
        
        # Crop from the source video, then scale to fill 1080x1920
        filter_parts.append(
            f"[0:v]crop={cw}:{ch}:{cx}:{cy},"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920[zoom{i}]"
        )
        
        # Overlay the zoomed crop onto the main stream, enabled only during the zoom window
        filter_parts.append(
            f"{overlay_chain}[zoom{i}]overlay=0:0:enable='between(t,{t_start:.2f},{t_end:.2f})'[v{i}]"
        )
        overlay_chain = f"[v{i}]"
    
    # Final output label
    filter_complex = ";".join(filter_parts)
    
    zoomed_path = str(OUTPUT_DIR / "zoomed_video.mp4")
    # -map with the final labeled stream output (e.g. "[v2]")
    cmd = [
        "ffmpeg", "-y", "-i", raw_video,
        "-filter_complex", filter_complex,
        "-map", overlay_chain,
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        zoomed_path,
    ]
    
    print(f"[MUXER] 🎯 Running zoom crop FFmpeg pass...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"[MUXER] ⚠️  Zoom crop failed, using original video")
        print(f"           {result.stderr[-300:]}")
        return raw_video
    
    print(f"[MUXER] ✅ Zoomed video → {zoomed_path}")
    return zoomed_path


def _apply_sequential_reveals(raw_video: str, reveal_cues: list[dict]) -> str:
    """
    Overlays high-res sequential snapshots.
    We center them in the 1080x1920 video and scale to completely overwrite the screen, 
    forming a massive jump-cut pop-in sequence holding 0.6 seconds per step.
    """
    if not reveal_cues:
        return raw_video

    filter_parts = []
    overlay_chain = "[0:v]"
    inputs = []
    
    for i, cue in enumerate(reveal_cues):
        inputs.append(cue["screenshot"])
        t_start = cue["timestamp"]
        t_end = t_start + 0.6
        img_in = i + 1

        # Use force_original_aspect_ratio=decrease and pad with black borders
        filter_parts.append(
            f"[{img_in}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black[rev_{i}]"
        )
        filter_parts.append(
            f"{overlay_chain}[rev_{i}]overlay=0:0:enable='between(t,{t_start:.2f},{t_end:.2f})'[v{i}]"
        )
        overlay_chain = f"[v{i}]"
        
    filter_complex = ";".join(filter_parts)
    revealed_path = str(OUTPUT_DIR / "revealed_video.mp4")
    
    cmd = ["ffmpeg", "-y", "-i", raw_video]
    for img in inputs:
        cmd.extend(["-loop", "1", "-t", "60", "-i", img])
        
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", overlay_chain,
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        revealed_path,
    ])
    
    print(f"[MUXER] 🎯 Running sequential reveal FFmpeg pass...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("[MUXER] ⚠️  Sequential reveal crop failed")
        print(f"           {result.stderr[-500:]}")
        return raw_video
        
    print(f"[MUXER] ✅ Revealed video → {revealed_path}")
    return revealed_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    global OLLAMA_MODEL

    parser = argparse.ArgumentParser(
        description="🎬 json2xzky Autonomous Video Factory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline from text script:
  python main_factory.py assets/example/example_script.txt

  # Skip Ollama (use existing JSON):
  python main_factory.py assets/example/example_scenario.json --skip-parse

  # Only parse (no recording):
  python main_factory.py script.txt --parse-only

  # Only mux (use existing raw_video + timeline):
  python main_factory.py --mux-only
        """
    )
    parser.add_argument("input", nargs="?", help="Input .txt script or .json scenario file")
    parser.add_argument("--skip-parse", action="store_true",
                        help="Input is already a .json — skip Ollama parsing")
    parser.add_argument("--parse-only", action="store_true",
                        help="Only parse text → JSON, don't record or mux")
    parser.add_argument("--mux-only", action="store_true",
                        help="Only run the FFmpeg muxer on existing output/ files")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Skip MyInstants audio fetching")
    parser.add_argument("--model", default=None,
                        help=f"Ollama model name (default: {OLLAMA_MODEL})")
    parser.add_argument("-o", "--output-json", default=None,
                        help="Output path for the generated scenario JSON")

    args = parser.parse_args()

    if args.model:
        OLLAMA_MODEL = args.model

    # ── Mux‑only mode ─────────────────────────────────────────────────
    if args.mux_only:
        print("\n╔═══════════════════════════════════════╗")
        print("║     🎵 MUXER ONLY MODE               ║")
        print("╚═══════════════════════════════════════╝\n")
        mux_audio_video()
        return

    if not args.input:
        parser.print_help()
        sys.exit(1)

    input_path = Path(args.input)

    print("\n╔═══════════════════════════════════════╗")
    print("║  🎬 json2xzky AUTONOMOUS FACTORY       ║")
    print("╚═══════════════════════════════════════╝\n")

    # ── Step 1: Parse ─────────────────────────────────────────────────
    if args.skip_parse or input_path.suffix == ".json":
        print(f"[PIPELINE] 📂 Using existing JSON: {input_path}")
        scenario = json.loads(input_path.read_text(encoding="utf-8"))
        scenario = _apply_sequential_reveal_groups(scenario)
        json_file = str(input_path)
    else:
        print("[PIPELINE] ═══ STEP 1/4: THE BRAIN ═══")
        json_file = args.output_json or str(input_path.with_suffix(".json"))
        scenario = parse_text_to_json(str(input_path), json_file)

    if args.parse_only:
        print(f"\n[PIPELINE] ✅ Parse complete. JSON saved to {json_file}")
        return

    # ── Step 2: Fetch Audio ───────────────────────────────────────────
    if not args.no_fetch:
        print("\n[PIPELINE] ═══ STEP 2/4: THE FETCHER ═══")
        try:
            scenario = resolve_audio_assets(scenario)
            # Re-save the mutated JSON
            Path(json_file).write_text(
                json.dumps(scenario, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except ImportError:
            print("[FETCHER] ⚠️  `requests` or `beautifulsoup4` not installed — skipping")
    else:
        print("\n[PIPELINE] ⏭️  Skipping audio fetch (--no-fetch)")

    # ── Step 3: Record ────────────────────────────────────────────────
    print("\n[PIPELINE] ═══ STEP 3/4: THE ACTOR ═══")
    raw_video, audio_timeline, camera_cues, reveal_cues = record_simulation(json_file)

    # ── Step 4: Mux ───────────────────────────────────────────────────
    print("\n[PIPELINE] ═══ STEP 4/4: THE MUXER ═══")
    final = mux_audio_video(raw_video, audio_timeline, camera_cues, reveal_cues)

    print(f"\n╔═══════════════════════════════════════╗")
    print(f"║  ✅ PIPELINE COMPLETE                  ║")
    print(f"║  📁 {final:<36s} ║")
    print(f"╚═══════════════════════════════════════╝\n")


if __name__ == "__main__":
    main()
