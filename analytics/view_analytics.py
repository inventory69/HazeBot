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
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("PROD_MODE="):
                        value = line.split("=", 1)[1].strip().strip('"').strip("'")
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
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind to (default: localhost, use 0.0.0.0 for all interfaces)",
    )
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()

    # Change to parent directory (HazeBot root) for data access
    script_dir = Path(__file__).parent.parent

    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(script_dir), **kwargs)

        def do_GET(self):
            # Proxy API requests to the bot's API server
            if self.path.startswith("/api/"):
                self.proxy_to_api()
                return
            # Serve login page (strip query parameters)
            elif self.path.startswith("/login") or self.path.startswith("/analytics/login"):
                self.path = "/analytics/login.html"
                super().do_GET()
                return
            # Redirect /analytics to /analytics/ (with trailing slash)
            elif self.path == "/analytics":
                self.send_response(301)
                self.send_header("Location", "/analytics/")
                self.end_headers()
                return
            # Redirect /analytics/ to dashboard
            elif self.path == "/analytics/":
                self.send_response(301)
                self.send_header("Location", "/analytics/analytics_dashboard.html")
                self.end_headers()
                return
            # Redirect root to analytics dashboard
            elif self.path == "/":
                self.send_response(301)
                self.send_header("Location", "/analytics/analytics_dashboard.html")
                self.end_headers()
                return
            # Allow direct access to analytics_dashboard.html
            elif self.path == "/analytics_dashboard.html":
                self.path = "/analytics/analytics_dashboard.html"
            super().do_GET()

        def proxy_to_api(self):
            """Proxy API requests to the bot's Flask API server"""
            import urllib.request
            import json

            # Try multiple API endpoints (Docker, Pterodactyl, localhost)
            # Priority order: Docker container IP from Nginx config first
            api_endpoints = [
                ("172.18.0.2", 5070),  # Docker container (Pterodactyl - from nginx config)
                ("172.18.0.1", 5070),  # Docker gateway (Pterodactyl network)
                ("172.17.0.1", 5070),  # Docker default bridge network
                ("host.docker.internal", 5070),  # Docker Desktop (Windows/Mac)
                ("localhost", 5070),  # Native (non-Docker)
            ]

            # Try each endpoint until one works
            last_error = None
            for api_host, api_port in api_endpoints:
                api_url = f"http://{api_host}:{api_port}{self.path}"

                try:
                    print(f"🔄 Trying API: {api_url}")

                    # Forward request to API server
                    with urllib.request.urlopen(api_url, timeout=2) as response:
                        data = response.read()

                        # Send successful response
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", len(data))
                        self.end_headers()
                        self.wfile.write(data)

                        print(f"✅ API request successful via {api_host}:{api_port}")
                        return  # Success! Exit function

                except urllib.error.URLError as e:
                    last_error = f"{api_host}:{api_port} - {e}"
                    print(f"❌ Failed: {api_host}:{api_port} - {e}")
                    continue  # Try next endpoint
                except Exception as e:
                    last_error = f"{api_host}:{api_port} - {e}"
                    print(f"❌ Error: {api_host}:{api_port} - {e}")
                    continue  # Try next endpoint

            # All endpoints failed
            print(f"❌ All API endpoints failed. Last error: {last_error}")
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_msg = {
                "error": "API server not reachable",
                "details": last_error,
                "tried_endpoints": [f"{h}:{p}" for h, p in api_endpoints],
                "hint": "Make sure the bot is running (API server on port 5070). Check Docker network or firewall.",
            }
            self.wfile.write(json.dumps(error_msg).encode())

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
            print("   Or use a different port: --port <other-port>")
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
