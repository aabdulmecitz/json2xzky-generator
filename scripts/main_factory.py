#!/usr/bin/env python3
"""
main_factory.py — Autonomous Beluga Video Factory
=================================================
Converts a raw scenario.txt → structured scenario.json → High-Res Screenshots 
→ FFmpeg slideshow → final_video.mp4 (1080p Horizontal)

Pipeline:
  1. THE BRAIN   - Ollama LLM parses raw script into JSON.
  2. THE FETCHER - Downloads missing audio/meme sounds.
  3. THE ACTOR   - Playwright renders the UI and takes 1080p screenshots.
  4. THE MUXER   - FFmpeg compiles shots & audio into a punchy jump-cut video.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import threading
import http.server
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths & Setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR   = PROJECT_ROOT / "assets"
SOUNDS_DIR   = ASSETS_DIR / "sounds" / "mp3"
OUTPUT_DIR   = PROJECT_ROOT / "output"
FRAMES_DIR   = OUTPUT_DIR / "frames"

for d in [SOUNDS_DIR, OUTPUT_DIR, FRAMES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
USER_AGENT   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# ═══════════════════════════════════════════════════════════════════════════
# 1. THE BRAIN — Ollama Script Parsing
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a Discord scenario JSON generator.
Input: A plain-text chat script.
Output: A SINGLE valid JSON array of objects.

Fields:
  - "id": int
  - "user_id": str (username)
  - "message_content": str
  - "action": "join", "typing", "message", "reply", "add_reaction", "system_message", "send_attachment"
  - "reply_to_id": int | null
  - "pause_after": float (seconds)
  - "sound": str | null (e.g. "vineboom")
  - "zoom": bool (true for punchlines/funny moments)

RULES:
• Always emit a "typing" entry BEFORE a "message" entry.
• Use "zoom": true for dramatic or funny reveals (Beluga style).
• Output ONLY the JSON array."""

def _legacy_parse(raw_text: str):
    lines = [l.rstrip() for l in raw_text.splitlines() if l.strip()]
    entries = []
    current_user = None
    msg_id = 0

    for line in lines:
        m = re.match(r"WELCOME\s+(\S+)\$\^([\d.]+)#!(\w+)", line)
        if m:
            msg_id += 1
            entries.append({
                "id": msg_id, "user_id": m.group(1), "message_content": "", "action": "join",
                "pause_after": float(m.group(2)), "sound": m.group(3)
            })
            current_user = None
            continue

        m = re.match(r"^(\w+):\s*$", line)
        if m:
            current_user = m.group(1)
            continue

        m = re.match(r"^(.+)\$\^([\d.]+)#!(\w+)\s*$", line)
        if m and current_user:
            text = m.group(1).strip()
            delay = float(m.group(2))
            sound = m.group(3)

            msg_id += 1
            entries.append({
                "id": msg_id, "user_id": current_user, "message_content": text, "action": "typing",
                "pause_after": 0.0, "sound": None
            })

            msg_id += 1
            entries.append({
                "id": msg_id, "user_id": current_user, "message_content": text, "action": "message",
                "pause_after": delay, "sound": sound,
                "zoom": sound in ("vineboom", "explosion", "scary", "hehascome", "error")
            })

    return entries


def parse_text_to_json(text_file: str, output_json: str):
    text_path = Path(text_file)
    raw_text = text_path.read_text(encoding="utf-8")
    
    try:
        import ollama
        print(f"[BRAIN] 🧠 Asking {OLLAMA_MODEL} to parse the script...")
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": raw_text}],
            options={"temperature": 0.1},
        )
        content = response["message"]["content"]
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"```\s*$", "", content, flags=re.MULTILINE)
        scenario = json.loads(content.strip())
    except Exception as e:
        print(f"[BRAIN] ⚠️ Ollama error ({e}) — using LEGACY parser fallback")
        scenario = _legacy_parse(raw_text)

    Path(output_json).write_text(json.dumps(scenario, indent=2, ensure_ascii=False), encoding="utf-8")
    return scenario

# ═══════════════════════════════════════════════════════════════════════════
# 2. THE FETCHER — Dynamic Audio Asset Resolution
# ═══════════════════════════════════════════════════════════════════════════

def resolve_audio_assets(scenario: list):
    import requests
    from bs4 import BeautifulSoup
    
    needed = set()
    for entry in scenario:
        s = entry.get("sound")
        if s and not (SOUNDS_DIR / f"{s}.mp3").exists():
            needed.add(s)
            
    if not needed: return scenario

    print(f"[FETCHER] 🔎 Fetching {len(needed)} missing sounds from MyInstants...")
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for query in needed:
        try:
            search_url = f"https://www.myinstants.com/en/search/?name={urllib.parse.quote_plus(query)}"
            resp = session.get(search_url, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            mp3_url = None
            btn = soup.select_one(".small-button")
            if btn:
                match = re.search(r"play\('(.*?\.mp3)'", btn.get("onclick", ""))
                if match: mp3_url = match.group(1)
            
            if mp3_url:
                if mp3_url.startswith("//"): mp3_url = "https:" + mp3_url
                elif mp3_url.startswith("/"): mp3_url = "https://www.myinstants.com" + mp3_url
                
                audio_data = session.get(mp3_url).content
                (SOUNDS_DIR / f"{query}.mp3").write_bytes(audio_data)
                print(f"[FETCHER] ✅ Got {query}.mp3")
        except:
            print(f"[FETCHER] ❌ Failed {query}")
            
    return scenario

# ═══════════════════════════════════════════════════════════════════════════
# 3. THE ACTOR — Playwright Screenshot Engine
# ═══════════════════════════════════════════════════════════════════════════

def record_simulation(json_path: Path):
    scenario = json.loads(json_path.read_text(encoding="utf-8"))
    
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)
        def log_message(self, format, *args): pass

    server = http.server.ThreadingHTTPServer(("0.0.0.0", 0), QuietHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    
    url = f"http://127.0.0.1:{port}/web_player/index.html"
    frame_timeline = []
    audio_timeline = []
    current_time = 0.0

    CPS = 8.0 # Reading speed
    
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        # Use an 800px wide, very tall viewport so messages wrap correctly, but height isn't constrained
        # scale_factor=2 gives high resolution 1600px width images.
        context = browser.new_context(viewport={"width": 800, "height": 8000}, device_scale_factor=2)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        
        print(f"[ACTOR] 📸 Generating {len(scenario)} dynamic jump-cut frames...")
        for i, entry in enumerate(scenario):
            action = entry.get("action", "message")
            page.evaluate(f"window.renderUpToStep({i}, {json.dumps(scenario)})")
            
            # Wait for all avatars to load
            page.evaluate("""
                () => new Promise(resolve => {
                    if (document.images.length === 0) return resolve();
                    let loaded = 0;
                    for (let img of document.images) {
                        if (img.complete) loaded++;
                        else {
                            img.onload = () => { loaded++; if (loaded === document.images.length) resolve(); };
                            img.onerror = () => { loaded++; if (loaded === document.images.length) resolve(); };
                        }
                    }
                    if (loaded >= document.images.length) resolve();
                })
            """)

            # Capture Dynamic Vertical Bounding Box
            bbox = page.evaluate("""
                () => {
                    const list = document.getElementById('messages-list');
                    let minY = 99999, maxY = 0;
                    let found = false;
                    for (const child of list.children) {
                        const rect = child.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0 || child.style.display === 'none') continue;
                        found = true;
                        if (rect.y < minY) minY = rect.y;
                        if (rect.bottom > maxY) maxY = rect.bottom;
                    }
                    const typing = document.getElementById('typing-indicator');
                    if (typing && !typing.classList.contains('hidden')) {
                        const rect = typing.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            found = true;
                            if (rect.y < minY) minY = rect.y;
                            if (rect.bottom > maxY) maxY = rect.bottom;
                        }
                    }
                    if (!found) return null;
                    // Keep width exactly the viewport width (800) so it scales consistently
                    return {
                        x: 0,
                        y: Math.max(0, minY - 16),
                        width: 800,
                        height: (maxY - minY) + 32
                    };
                }
            """)

            frame_path = FRAMES_DIR / f"frame_{i:04d}.png"
            if bbox:
                # Add a tiny fix: if height is weirdly small, just bump it slightly
                if bbox["height"] < 10: bbox["height"] = 10
                page.screenshot(path=str(frame_path), clip=bbox)
            else:
                page.screenshot(path=str(frame_path)) # Fallback

            # Duration logic
            if action == "typing":
                duration = 0.6 # Short pop for typing
            else:
                msg = str(entry.get("message_content", ""))
                duration = max(1.0, min(3.5, len(msg) / CPS))
                duration += float(entry.get("pause_after", 0))
                
                # Audio logic
                s = entry.get("sound")
                if s and (SOUNDS_DIR / f"{s}.mp3").exists():
                    audio_timeline.append({"file": str(SOUNDS_DIR / f"{s}.mp3"), "timestamp": current_time})
                elif action in ["message", "reply"]:
                    audio_timeline.append({"file": str(SOUNDS_DIR / "message.mp3"), "timestamp": current_time})

            frame_timeline.append({"path": str(frame_path), "duration": duration})
            current_time += duration
            
        browser.close()
    
    server.shutdown()
    return frame_timeline, audio_timeline

# ═══════════════════════════════════════════════════════════════════════════
# 4. THE MUXER — FFmpeg Slideshow Compiler
# ═══════════════════════════════════════════════════════════════════════════

def mux_audio_video(frame_timeline, audio_timeline):
    if not frame_timeline: return None
    
    concat_file = OUTPUT_DIR / "concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for fr in frame_timeline:
            # properly escape the path for concat demuxer
            p = str(fr['path']).replace("'", "'\\''")
            f.write(f"file '{p}'\nduration {fr['duration']}\n")
        
        last_p = str(frame_timeline[-1]['path']).replace("'", "'\\''")
        f.write(f"file '{last_p}'\n")

    raw_vid = OUTPUT_DIR / "raw_slideshow.mp4"
    print("[MUXER] 🎬 Compiling slideshow video...")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-vf", "scale=1920:980:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:100:color=black", str(raw_vid)
    ], capture_output=True)

    final_vid = OUTPUT_DIR / "final_video.mp4"
    if not audio_timeline:
        import shutil
        shutil.copy2(raw_vid, final_vid)
        return str(final_vid)

    print(f"[MUXER] 🎵 Mixing {len(audio_timeline)} audio layers...")
    cmd = ["ffmpeg", "-y", "-i", str(raw_vid)]
    for ev in audio_timeline: cmd.extend(["-i", ev["file"]])
    
    filters = []
    for i, ev in enumerate(audio_timeline):
        ms = int(ev['timestamp'] * 1000)
        filters.append(f"[{i+1}:a]adelay={ms}|{ms}[a{i}]")
    
    mix = "".join(f"[a{i}]" for i in range(len(audio_timeline)))
    filters.append(f"{mix}amix=inputs={len(audio_timeline)}:dropout_transition=0[aout]")
    
    cmd.extend(["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", str(final_vid)])
    subprocess.run(cmd, capture_output=True)
    
    return str(final_vid)

# ═══════════════════════════════════════════════════════════════════════════
# Main CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    global OLLAMA_MODEL
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--skip-parse", action="store_true")
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--model", default=OLLAMA_MODEL)
    args = parser.parse_args()

    if args.model:
        OLLAMA_MODEL = args.model

    input_path = Path(args.input)
    json_path = input_path.with_suffix(".json")

    # Step 1: Brain
    if args.skip_parse:
        scenario = json.loads(json_path.read_text())
    else:
        scenario = parse_text_to_json(args.input, str(json_path))

    # Step 2: Fetcher
    if not args.no_fetch:
        resolve_audio_assets(scenario)

    # Step 3: Actor
    frames, audio = record_simulation(json_path)

    # Step 4: Muxer
    final = mux_audio_video(frames, audio)
    print(f"\n[PIPELINE] 🏰 BELUGA VIDEO COMPLETE: {final}")

if __name__ == "__main__":
    main()
