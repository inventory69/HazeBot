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
import socketserver
import webbrowser
from pathlib import Path


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

    with socketserver.TCPServer((args.host, args.port), CustomHandler) as httpd:
        if args.host == "0.0.0.0":
            url = f"http://<your-server-ip>:{args.port}/analytics/analytics_dashboard.html"
        else:
            url = f"http://{args.host}:{args.port}/analytics/analytics_dashboard.html"

        print("=" * 60)
        print("📊 HazeBot Analytics Dashboard Server")
        print("=" * 60)
        print(f"\n✅ Server started on {args.host}:{args.port}")
        print(f"🌐 Dashboard URL: {url}\n")
        print("Press Ctrl+C to stop the server\n")

        if not args.no_browser:
            print("🚀 Opening dashboard in browser...")
            webbrowser.open(url)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped. Goodbye!")


if __name__ == "__main__":
    main()
