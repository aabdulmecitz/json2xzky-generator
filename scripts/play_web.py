import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8000

def run_server():
    # Change working directory to ONE LEVEL UP from scripts to serve both web_player and assets
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    os.chdir(root_dir)
    
    Handler = http.server.SimpleHTTPRequestHandler
    
    # Use fixed port 55777, bind to 0.0.0.0 to ensure Windows can access it from WSL
    with socketserver.TCPServer(("0.0.0.0", 55777), Handler) as httpd:
        port = 55777
        url = f"http://localhost:{port}/web_player/index.html"
        print(f"Serving at {url}")
        print("Opening Web Simulator in your default browser...")
        print("(Press CTRL+C in this terminal to stop the server once you are done recording.)")
        
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")

if __name__ == "__main__":
    run_server()
