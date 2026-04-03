import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    scenario_path = Path("assets/example/video.json").resolve()
    scenario_data = scenario_path.read_text(encoding="utf-8")
    
    with sync_playwright() as pw:
        browser = pw.firefox.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1080, "height": 1920}, device_scale_factor=1.0)
        page = ctx.new_page()
        
        # Open via local server if possible, or file://
        # Let's use the local server like the main script does
        import http.server, threading
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        
        url = f"http://127.0.0.1:{port}/web_player/index.html"
        page.goto(url, wait_until="load")
        
        page.evaluate(f"""
            scenarioEntries = {scenario_data};
            const overlay = document.getElementById('start-overlay');
            if (overlay) overlay.style.display = 'none';
            document.body.classList.add('instant-mode');
            isInstant = true;
            runSimulation();
        """)
        
        page.wait_for_function("() => window.__simulationDone === true", timeout=30_000)
        page.wait_for_timeout(1000)
        
        # Take full screenshot BEFORE hiding
        page.screenshot(path="full_before.png", full_page=True)
        
        # Hide all except 15 and 17
        all_dom_ids = page.evaluate("""
            Array.from(document.querySelectorAll('[id^="msg_"]')).map(el => parseInt(el.id.replace('msg_','')))
        """)
        
        # Step 0 for group 1 (msg 15)
        page.evaluate(f"""
            {json.dumps(all_dom_ids)}.forEach(id => {{
                let el = document.getElementById('msg_' + id);
                if (el) el.style.display = (id === 15) ? 'flex' : 'none';
            }});
        """)
        
        page.wait_for_timeout(500)
        page.screenshot(path="full_after.png", full_page=True)
        
        bbox = page.evaluate("""
            (() => {
                let el = document.getElementById('msg_15');
                let r = el.getBoundingClientRect();
                return { x: r.x, y: r.y, w: r.width, h: r.height };
            })()
        """)
        print("BBOX:", bbox)
        
        clip = {"x": bbox["x"], "y": bbox["y"], "width": bbox["w"], "height": bbox["h"]}
        page.screenshot(path="clip_test.png", clip=clip)
        
        browser.close()
        server.shutdown()

if __name__ == "__main__":
    main()
