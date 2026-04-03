#!/usr/bin/env python3
"""
beluga_render.py — Beluga-Style Horizontal Video Renderer
==========================================================
Reads a scenario JSON and produces a 1920x1080 MP4 where every
message appears as a high-res Discord element screenshot centered
on a black background — exactly like Beluga/Splurt YouTube videos.

Usage:
  python3 scripts/beluga_render.py assets/example/example_scenario.json
"""

import json
import subprocess
import sys
import time
import http.server
import threading
import tempfile
import shutil
from pathlib import Path

# ─────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR   = PROJECT_ROOT / "assets"
SOUNDS_DIR   = ASSETS_DIR / "sounds" / "mp3"
WEB_DIR      = PROJECT_ROOT / "web_player"
OUTPUT_DIR   = PROJECT_ROOT / "output"
FRAMES_DIR   = OUTPUT_DIR / "beluga_frames"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080   # Final video resolution
DPI  = 3            # Screenshot scale (3x = extremely sharp)

MESSAGE_ACTIONS = {"message", "send_message", "reply", "send_attachment", "send_voice_note"}


def start_http_server():
    """Spin up a local server so web_player can load assets without CORS errors."""
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)
        def log_message(self, *a): pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Q)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def group_messages(scenario: list) -> list:
    """
    Group consecutive messages by the same user.
    Returns a list of groups. Each group = list of message entries.
    Non-message actions (join, typing, etc.) become their own single-item group
    with type='system'.
    """
    groups = []
    i = 0
    while i < len(scenario):
        entry = scenario[i]
        action = entry.get("action", "")

        if action in MESSAGE_ACTIONS:
            # Start a group for this user
            user = entry.get("user_id")
            group = [entry]
            j = i + 1
            while j < len(scenario):
                nxt = scenario[j]
                nxt_action = nxt.get("action", "")
                # Skip typing entries that belong to the same user
                if nxt_action == "typing" and nxt.get("user_id") == user:
                    j += 1
                    continue
                if nxt_action in MESSAGE_ACTIONS and nxt.get("user_id") == user:
                    group.append(nxt)
                    j += 1
                else:
                    break
            groups.append({"type": "messages", "user": user, "entries": group})
            i = j
        elif action == "typing":
            # Skip standalone typing indicators
            i += 1
        else:
            # System events (join, leave, etc.) — collect their pause
            groups.append({"type": "system", "entry": entry})
            i += 1

    return groups


def capture_frames(scenario: list, port: int) -> list:
    """
    Uses Playwright to:
      1. Load the Discord simulator in instant mode (all messages rendered at once)
      2. For each message group, hide/show elements to capture expanding blocks
         (step 1 = msg1, step 2 = msg1+msg2, step 3 = msg1+msg2+msg3)
    
    Returns a list of frame dicts:
      { "png": "/abs/path/to/frame.png", "duration": float (seconds),
        "audio": [{"file": ..., "timestamp": ...}] }
    """
    from playwright.sync_api import sync_playwright

    url = f"http://127.0.0.1:{port}/web_player/index.html"
    scenario_json = json.dumps(scenario)
    groups = group_messages(scenario)

    frames = []
    t_cursor = 0.0  # running timestamp for audio sync

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"]
        )
        ctx = browser.new_context(
            viewport={"width": 1080, "height": 1920},
            device_scale_factor=DPI
        )
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Inject scenario and run in instant/hidden mode
        page.evaluate(f"""
            window.scenarioEntries = {scenario_json};
            const overlay = document.getElementById('start-overlay');
            if (overlay) overlay.style.display = 'none';
            document.body.classList.add('recording-mode');
            isInstant = true;
            runSimulation();
        """)
        page.wait_for_timeout(800)

        # --- Gather all message IDs in order ---
        all_msg_ids = [e["id"] for e in scenario if e.get("action") in MESSAGE_ACTIONS]

        # Hide all messages to start
        page.evaluate(f"""
            var ids = {json.dumps(all_msg_ids)};
            ids.forEach(function(id) {{
                var el = document.getElementById('msg_' + id);
                if (el) el.style.display = 'none';
            }});
        """)

        shown_ids = []  # messages currently visible

        for grp in groups:
            if grp["type"] == "system":
                entry = grp["entry"]
                # For system messages (join/leave) just advance the timeline
                pause = entry.get("pause_after", 1.0)
                audio = []
                if entry.get("sound"):
                    f = str(SOUNDS_DIR / f"{entry['sound']}.mp3")
                    if Path(f).exists():
                        audio.append({"file": f, "timestamp": t_cursor})
                t_cursor += pause
                # No visual frame for system events (they show inline in next message)
                continue

            # Message group
            entries = grp["entries"]
            for step_idx, entry in enumerate(entries):
                msg_id = entry["id"]

                # Show this message
                page.evaluate(f"""
                    var el = document.getElementById('msg_{msg_id}');
                    if (el) el.style.display = 'flex';
                """)
                shown_ids.append(msg_id)
                page.wait_for_timeout(60)

                # Scroll to bottom so latest message is in view
                page.evaluate("document.getElementById('chat-container').scrollTop = 99999;")
                page.wait_for_timeout(40)

                # Get bounding box of the whole visible block
                # (from first shown message in this group to current)
                group_visible_ids = [e["id"] for e in entries[:step_idx + 1]]
                bbox = page.evaluate(f"""
                    (function() {{
                        var ids = {json.dumps(group_visible_ids)};
                        var minX=9999,minY=9999,maxX=0,maxY=0,f=false;
                        ids.forEach(function(id) {{
                            var el = document.getElementById('msg_'+id);
                            if(el) {{
                                var r = el.getBoundingClientRect();
                                minX=Math.min(minX,r.x); minY=Math.min(minY,r.y);
                                maxX=Math.max(maxX,r.x+r.width);
                                maxY=Math.max(maxY,r.y+r.height);
                                f=true;
                            }}
                        }});
                        return f ? {{x:minX,y:minY,w:maxX-minX,h:maxY-minY}} : null;
                    }})()
                """)

                if not bbox or bbox["w"] < 5 or bbox["h"] < 5:
                    t_cursor += entry.get("pause_after", 1.0)
                    continue

                # Small padding
                pad = 12
                clip = {
                    "x": max(0, bbox["x"] - pad),
                    "y": max(0, bbox["y"] - pad),
                    "width":  min(1080, bbox["w"] + pad * 2),
                    "height": min(1920, bbox["h"] + pad * 2),
                }

                shot_path = FRAMES_DIR / f"frame_{msg_id:04d}_s{step_idx}.png"
                page.screenshot(path=str(shot_path), clip=clip)

                # Audio events for this entry
                audio_events = []
                if entry.get("sound"):
                    f = str(SOUNDS_DIR / f"{entry['sound']}.mp3")
                    if Path(f).exists():
                        audio_events.append({"file": f, "timestamp": t_cursor})

                pause = entry.get("pause_after", 1.5)
                frames.append({
                    "png": str(shot_path),
                    "duration": pause,
                    "audio": audio_events,
                })
                t_cursor += pause

        ctx.close()
        browser.close()

    print(f"[RENDER] ✅ Captured {len(frames)} frames")
    return frames


def build_video(frames: list) -> str:
    """
    Assemble all frames into a 1920x1080 MP4 using FFmpeg.
    Each frame is shown for its duration, scaled/padded to 1920x1080 black canvas.
    Audio events are layered via adelay.
    """
    if not frames:
        print("[RENDER] ❌ No frames to render!")
        sys.exit(1)

    # ── Build concat list ──────────────────────────────────────────────
    concat_txt = OUTPUT_DIR / "beluga_concat.txt"
    with open(concat_txt, "w") as f:
        for fr in frames:
            f.write(f"file '{fr['png']}'\n")
            # FFmpeg concat demuxer duration in seconds
            f.write(f"duration {fr['duration']:.3f}\n")
        # Repeat last frame (ffmpeg concat needs it)
        f.write(f"file '{frames[-1]['png']}'\n")

    # ── Step 1: Build silent slideshow at 30fps ───────────────────────
    silent_path = str(OUTPUT_DIR / "beluga_silent.mp4")
    cmd_silent = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        # Scale+pad to 1920x1080 with black bars
        "-vf", (
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1,fps=30"
        ),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        silent_path,
    ]
    print("[RENDER] 🎞️  Building slideshow...")
    r = subprocess.run(cmd_silent, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[RENDER] ❌ FFmpeg error (silent):\n{r.stderr[-800:]}")
        sys.exit(1)

    # ── Step 2: Collect all audio events with absolute timestamps ─────
    all_audio = []
    for fr in frames:
        all_audio.extend(fr.get("audio", []))

    # Deduplicate
    seen = set()
    unique_audio = []
    for ev in all_audio:
        key = (ev["file"], round(ev["timestamp"], 2))
        if key not in seen and Path(ev["file"]).exists():
            seen.add(key)
            unique_audio.append(ev)

    if not unique_audio:
        # No audio — just copy silent as final
        final_path = str(OUTPUT_DIR / "beluga_final.mp4")
        shutil.copy2(silent_path, final_path)
        print(f"[RENDER] ✅ Final (no audio): {final_path}")
        return final_path

    # ── Step 3: Layer audio ───────────────────────────────────────────
    final_path = str(OUTPUT_DIR / "beluga_final.mp4")
    cmd = ["ffmpeg", "-y", "-i", silent_path]
    for ev in unique_audio:
        cmd.extend(["-i", ev["file"]])

    filter_parts = []
    for i, ev in enumerate(unique_audio):
        ms = int(ev["timestamp"] * 1000)
        filter_parts.append(f"[{i+1}:a]adelay={ms}|{ms}[a{i}]")

    mix = "".join(f"[a{i}]" for i in range(len(unique_audio)))
    filter_parts.append(f"{mix}amix=inputs={len(unique_audio)}:dropout_transition=0[aout]")

    cmd.extend([
        "-filter_complex", ";".join(filter_parts),
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        final_path,
    ])

    print(f"[RENDER] 🎵 Layering {len(unique_audio)} audio events...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[RENDER] ❌ FFmpeg audio error:\n{r.stderr[-500:]}")
        shutil.copy2(silent_path, final_path)

    print(f"[RENDER] ✅ Beluga video → {final_path}")
    return final_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/beluga_render.py <scenario.json>")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"❌ File not found: {json_path}")
        sys.exit(1)

    scenario = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"\n╔══════════════════════════════════════════╗")
    print(f"║  🎬 BELUGA RENDER — {json_path.name:<22s}║")
    print(f"╚══════════════════════════════════════════╝\n")
    print(f"[RENDER] 📂 {len(scenario)} events loaded")

    # Clean frames dir
    shutil.rmtree(FRAMES_DIR, ignore_errors=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    # Start local server
    srv, port = start_http_server()
    print(f"[RENDER] 🌐 Local server on http://127.0.0.1:{port}")

    try:
        frames = capture_frames(scenario, port)
        final = build_video(frames)
    finally:
        srv.shutdown()

    print(f"\n[RENDER] 🏁 Done! → {final}\n")


if __name__ == "__main__":
    main()
