#!/usr/bin/env python3
"""
HazeBot Analytics Dashboard Server
===================================
Simple HTTP server to view analytics dashboard locally.

Usage:
    python view_analytics.py [--port PORT]

Then open: http://localhost:8080
"""

import argparse
import http.server
import os
import socketserver
import webbrowser
from pathlib import Path

# Load .env file to check PROD_MODE
def load_prod_mode():
    """Load PROD_MODE from .env or Config.py"""
    # Try loading from .env with python-dotenv
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            prod_mode = os.getenv("PROD_MODE", "false").lower() == "true"
            print(f"✅ Loaded PROD_MODE from .env: {prod_mode}")
            return prod_mode
    except ImportError:
        pass
    
    # Fallback: Parse .env file manually
    try:
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('PROD_MODE='):
                        value = line.split('=', 1)[1].strip().strip('"').strip("'")
                        prod_mode = value.lower() == "true"
                        print(f"✅ Parsed PROD_MODE from .env: {prod_mode}")
                        return prod_mode
    except Exception as e:
        print(f"⚠️  Warning: Could not read .env: {e}")
    
    # Last fallback: Try importing Config.py
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import Config
        prod_mode = Config.PROD_MODE
        print(f"✅ Loaded PROD_MODE from Config.py: {prod_mode}")
        return prod_mode
    except Exception as e:
        print(f"⚠️  Warning: Could not load Config.py: {e}")
    
    print("⚠️  Warning: Defaulting to PROD_MODE=False")
    return False

PROD_MODE = load_prod_mode()
DATA_DIR = "Data" if PROD_MODE else "TestData"


def main():
    parser = argparse.ArgumentParser(description="Start HazeBot Analytics Dashboard")
    parser.add_argument("--port", type=int, default=8080, help="Port to serve on (default: 8080)")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind to (default: localhost, use 0.0.0.0 for all interfaces)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()

    # Change to parent directory (HazeBot root) for data access
    script_dir = Path(__file__).parent.parent

    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(script_dir), **kwargs)
        
        def do_GET(self):
            # Redirect root to analytics dashboard
            if self.path == '/':
                self.send_response(301)
                self.send_header('Location', '/analytics/analytics_dashboard.html')
                self.end_headers()
                return
            # Allow direct access to analytics_dashboard.html
            elif self.path == '/analytics_dashboard.html':
                self.path = '/analytics/analytics_dashboard.html'
            super().do_GET()

        def end_headers(self):
            # Allow CORS for local file access
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            super().end_headers()

    # Allow port reuse to prevent "Address already in use" errors
    socketserver.TCPServer.allow_reuse_address = True
    
    httpd = None
    try:
        httpd = socketserver.TCPServer((args.host, args.port), CustomHandler)
        
        if args.host == "0.0.0.0":
            url = f"http://<your-server-ip>:{args.port}/analytics/analytics_dashboard.html"
        else:
            url = f"http://{args.host}:{args.port}/analytics/analytics_dashboard.html"

        print("=" * 60)
        print("📊 HazeBot Analytics Dashboard Server")
        print("=" * 60)
        print(f"\n🔧 Mode: {'PRODUCTION' if PROD_MODE else 'DEVELOPMENT'}")
        print(f"📂 Data Directory: {DATA_DIR}/")
        print(f"✅ Server started on {args.host}:{args.port}")
        print(f"🌐 Dashboard URL: {url}\n")
        print("Press Ctrl+C to stop the server\n")

        if not args.no_browser:
            print("🚀 Opening dashboard in browser...")
            webbrowser.open(url)

        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"\n❌ Error: Port {args.port} is already in use!")
            print(f"💡 Try killing the process using: lsof -ti:{args.port} | xargs kill -9")
            print(f"   Or use a different port: --port <other-port>")
        else:
            print(f"\n❌ Server error: {e}")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
    finally:
        # Ensure proper cleanup
        if httpd:
            try:
                httpd.server_close()
                print("🧹 Server socket closed cleanly")
            except Exception as cleanup_error:
                print(f"⚠️  Cleanup warning: {cleanup_error}")


if __name__ == "__main__":
    main()
