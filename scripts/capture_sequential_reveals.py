#!/usr/bin/env python3
"""
capture_sequential_reveals.py
==============================
video.json senaryosunu okur, aynı kullanıcının üst üste attığı mesaj gruplarını
tespit eder ve Firefox Playwright ile "Sequential Reveal" (kademeli açılımlı)
yüksek çözünürlüklü ekran görüntüleri alır.

Her grup için:
  - reveal_g{N}_step0.png  →  Sadece 1. mesaj
  - reveal_g{N}_step1.png  →  1. + 2. mesaj birlikte
  - reveal_g{N}_step2.png  →  1. + 2. + 3. mesaj birlikte

Kullanım:
  python capture_sequential_reveals.py
  python capture_sequential_reveals.py --json ../assets/example/video.json
  python capture_sequential_reveals.py --scale 2.0 --min-group 2
"""

import argparse
import http.server
import json
import threading
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR   = PROJECT_ROOT / "output" / "sequential_reveals"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ────────────────────────────────────────────────────────────────────

# SADECE bu aksiyonlar appendMessage() → DOM'da #msg_N div'i oluşturur
DOM_MESSAGE_ACTIONS = {"message", "reply", "send_attachment", "send_message"}


def find_sequential_groups(scenario: list, min_count: int = 2) -> list[dict]:
    """
    Senaryo içinde aynı kullanıcının art arda gönderdiği GERÇEK mesajları gruplar.
    incoming_call, send_voice_note, join, leave, add_reaction, typing gibi
    aksiyonlar DOM'da #msg_N oluşturmaz — bunlar tamamen görmezden gelinir.
    """
    groups = []
    group_id = 1
    current_user = None
    current_ids  = []

    def flush():
        nonlocal group_id
        if len(current_ids) >= min_count:
            groups.append({
                "group_id": group_id,
                "user": current_user,
                "msg_ids": list(current_ids),
            })
            group_id += 1

    for entry in scenario:
        action = entry.get("action", "")
        if action not in DOM_MESSAGE_ACTIONS:
            continue  # typing, join, incoming_call, send_voice_note vb. → atla

        user = entry.get("user_id", "")
        mid  = entry.get("id")
        if mid is None:
            continue

        if user == current_user:
            current_ids.append(mid)
        else:
            flush()
            current_user = user
            current_ids  = [mid]

    flush()
    return groups


def start_local_server(root: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)
        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port   = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


# ── Core capture ───────────────────────────────────────────────────────────────

def capture_reveals(scenario_path: Path, scale: float, min_count: int, padding: int):
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    groups   = find_sequential_groups(scenario, min_count=min_count)

    if not groups:
        print(f"[CAPTURE] ⚠️  Hiç Sequential Reveal grubu bulunamadı (min={min_count}).")
        return

    total_steps = sum(len(g["msg_ids"]) for g in groups)
    print(f"[CAPTURE] 🔎 {len(groups)} grup bulundu, toplam {total_steps} screenshot alınacak.")

    server, port = start_local_server(PROJECT_ROOT)
    url = f"http://127.0.0.1:{port}/web_player/index.html"
    scenario_data = scenario_path.read_text(encoding="utf-8")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        # Tam sayfa çözünürlüğü için standart 1080 width veriyoruz
        browser = pw.firefox.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1080, "height": 1080},
            device_scale_factor=scale,
        )
        page = ctx.new_page()

        print(f"[CAPTURE] 🦊 Firefox başlatılıyor (scale={scale}x)…")
        page.goto(url, wait_until="load", timeout=30_000)

        # ── KÖKLÜ CSS MÜDAHALESİ ──
        # Discord player normalde kendi scroll'u olan sabit bir yüksekliğe sahip.
        # Screenshot için bunu bozup, düz bir resim kağıdına çeviriyoruz.
        # Böylece "sayfa aşağısında kalan görünmez element" saçmalığı tamamen bitiyor.
        page.add_style_tag(content="""
            * {
                -webkit-animation: none !important;
                animation: none !important;
                transition: none !important;
            }
            /* Tüm kayan kutuları iptal et, normal belge akışına (static) çevir */
            body, html, #viewport-wrapper, #discord-app, #main-view, .chat-container, #messages-list {
                height: auto !important;
                min-height: 0 !important;
                max-height: none !important;
                overflow: visible !important;
                position: static !important;
                transform: none !important;
            }
            /* Ekranı ortalamaya çalışan wrappers'dan kurtul */
            #discord-app {
                width: 1080px !important;
                margin: 0 !important;
                border-radius: 0 !important;
                box-shadow: none !important;
            }
            /* Sadece mesajlar ! Başlıkları ve giriş yerini yokediyoruz */
            #status-bar, #top-header, #bottom-input-bar, .welcome-header, .incoming-call-overlay {
                display: none !important;
                visibility: hidden !important;
            }
            /* Mesajların yanlardan çok yapışmaması için boşluk */
            .message {
                padding-left: 24px !important;
                padding-right: 24px !important;
            }
        """)

        # Simülasyonu instant modda başlat
        page.evaluate(f"""
            scenarioEntries = {scenario_data};
            const overlay = document.getElementById('start-overlay');
            if (overlay) overlay.style.display = 'none';
            document.body.classList.add('instant-mode');
            isInstant = true;
            runSimulation();
        """)

        print("[CAPTURE] ⏳ Simülasyon tamamlanıyor…")
        try:
            page.wait_for_function("() => window.__simulationDone === true", timeout=120_000)
            print("[CAPTURE] ✅ Simülasyon tamamlandı.")
        except Exception:
            print("[CAPTURE] ⚠️  __simulationDone gelmedi, yine de devam ediliyor.")

        page.wait_for_timeout(800)

        # DOM'da gerçekten var olan #msg_* ID'lerini tespit et
        all_dom_ids = page.evaluate("""
            (function() {
                var found = [];
                document.querySelectorAll('[id^="msg_"]').forEach(function(el) {
                    var n = parseInt(el.id.replace('msg_', ''), 10);
                    if (!isNaN(n)) found.push(n);
                });
                return found;
            })()
        """)

        # Tümünü gizle
        page.evaluate(f"""
            {json.dumps(all_dom_ids)}.forEach(function(id) {{
                var el = document.getElementById('msg_' + id);
                if (el) el.style.display = 'none';
            }});
        """)
        page.wait_for_timeout(200)

        # ── Her grup için kademeli screenshot ──
        captured = 0

        for g in groups:
            gid     = g["group_id"]
            user    = g["user"]
            msg_ids = g["msg_ids"]

            valid_ids = [mid for mid in msg_ids if mid in all_dom_ids]
            if not valid_ids: continue

            print(f"\n[CAPTURE] 📸 Grup {gid} — {user} ({len(valid_ids)} mesaj)")

            for step_idx in range(len(valid_ids)):
                # Bu adıma kadarkileri göster
                page.evaluate(f"""
                    var ids = {json.dumps(valid_ids)};
                    for (var i = 0; i < ids.length; i++) {{
                        var el = document.getElementById('msg_' + ids[i]);
                        if (el) el.style.display = (i <= {step_idx}) ? 'flex' : 'none';
                    }}
                """)
                page.wait_for_timeout(100)  # css reflow bekleyişi

                # Artık sayfada scrolling/clipping kalmadığı ve mesajlar 
                # belgenin EN TEPESİNDE (margin 0) dizileceği için 
                # bbox hesaplamak ve screenshot almak kusursuz çalışacak!
                bbox = page.evaluate(f"""
                    (function() {{
                        var ids = {json.dumps(valid_ids)};
                        var minX = 1e9, minY = 1e9, maxX = 0, maxY = 0, found = false;
                        for (var i = 0; i <= {step_idx}; i++) {{
                            var el = document.getElementById('msg_' + ids[i]);
                            if (!el || el.style.display === 'none') continue;
                            found = true;
                            var r = el.getBoundingClientRect();
                            if (r.x < minX) minX = r.x;
                            if (r.y < minY) minY = r.y;
                            if (r.x + r.width  > maxX) maxX = r.x + r.width;
                            if (r.y + r.height > maxY) maxY = r.y + r.height;
                        }}
                        if (!found) return null;
                        return {{ x: minX, y: minY, width: maxX - minX, height: maxY - minY }};
                    }})()
                """)

                if not bbox:
                    continue

                clip = {
                    "x":      max(0.0, bbox["x"] - padding),
                    "y":      max(0.0, bbox["y"] - padding),
                    "width":  bbox["width"]  + padding * 2,
                    "height": bbox["height"] + padding * 2,
                }

                shot_name = f"reveal_g{gid}_step{step_idx}.png"
                shot_path = OUTPUT_DIR / shot_name
                page.screenshot(path=str(shot_path), clip=clip)
                captured += 1

                size = shot_path.stat().st_size // 1024
                print(f"   ✅ step{step_idx} → {shot_name} [{clip['width']:.0f}×{clip['height']:.0f} @ {scale}x] ({size} KB)")

            # Grubun mesajlarını geri gizle
            page.evaluate(f"""
                {json.dumps(valid_ids)}.forEach(function(id) {{
                    var el = document.getElementById('msg_' + id);
                    if (el) el.style.display = 'none';
                }});
            """)

        ctx.close()
        browser.close()

    server.shutdown()
    print(f"\n[CAPTURE] 🎉 Tamamlandı! {captured} görsel → {OUTPUT_DIR}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🦊 Firefox Sequential Reveal Screenshot Capture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python capture_sequential_reveals.py
  python capture_sequential_reveals.py --json ../assets/example/video.json
  python capture_sequential_reveals.py --scale 3.0 --min-group 2 --padding 30
        """
    )
    parser.add_argument(
        "--json", default=str(PROJECT_ROOT / "assets/example/video.json"),
        help="Senaryo JSON dosyası"
    )
    parser.add_argument("--scale",     type=float, default=3.0,
                        help="Device pixel ratio (varsayılan: 3.0)")
    parser.add_argument("--min-group", type=int,   default=2,
                        help="Grupta min. mesaj sayısı (varsayılan: 2)")
    parser.add_argument("--padding",   type=int,   default=20,
                        help="Bbox etrafı boşluk px (varsayılan: 20)")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════╗")
    print("║  🦊 Sequential Reveal Capture Tool       ║")
    print("╚══════════════════════════════════════════╝\n")

    scenario_path = Path(args.json).resolve()
    if not scenario_path.exists():
        print(f"[ERROR] Dosya bulunamadı: {scenario_path}")
        return

    print(f"[CONFIG] Senaryo  : {scenario_path}")
    print(f"[CONFIG] Scale    : {args.scale}x")
    print(f"[CONFIG] Min-Grup : {args.min_group} mesaj")
    print(f"[CONFIG] Padding  : {args.padding}px")
    print(f"[CONFIG] Çıktı    : {OUTPUT_DIR}\n")

    capture_reveals(
        scenario_path=scenario_path,
        scale=args.scale,
        min_count=args.min_group,
        padding=args.padding,
    )


if __name__ == "__main__":
    main()
