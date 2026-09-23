"""
serve_dashboard.py - Lightweight local web server for Social Media ETL Visualizer.

Serves index.html and provides live API endpoints for PostgreSQL queries and pipeline execution.
Usage:
    python serve_dashboard.py [--port 8000]
"""

import http.server
import json
import os
import sys
import urllib.parse
import webbrowser
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from load.db import SessionLocal, SocialPost, test_connection
    from pipeline import run_pipeline
    DB_AVAILABLE = True
except Exception as e:
    print(f"[WARN] Database modules could not be imported: {e}")
    DB_AVAILABLE = False


class ETLDashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler serving index.html and live API routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("", "/"):
            self.path = "/index.html"
            return super().do_GET()

        if path == "/favicon.ico":
            svg = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='#3b82f6' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polygon points='12 2 2 7 12 12 22 7 12 2'/><polyline points='2 17 12 22 22 17'/><polyline points='2 12 12 17 22 12'/></svg>"""
            body = svg.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/status":
            self.handle_api_status()
            return

        if path == "/api/posts":
            self.handle_api_posts()
            return

        # Default static file handler
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/run-pipeline":
            self.handle_api_run_pipeline()
            return

        self.send_error(404, "Endpoint not found")

    def handle_api_status(self):
        """Return database connection status and total count."""
        db_connected = False
        post_count = 0
        error_msg = None

        if DB_AVAILABLE:
            try:
                with SessionLocal() as session:
                    post_count = session.query(SocialPost).count()
                    db_connected = True
            except Exception as e:
                error_msg = str(e)

        payload = {
            "status": "online",
            "db_connected": db_connected,
            "total_posts": post_count,
            "error": error_msg,
            "database": os.getenv("DB_NAME", "social_data"),
        }
        self._send_json(payload)

    def handle_api_posts(self):
        """Query posts directly from PostgreSQL and return JSON."""
        if not DB_AVAILABLE:
            self._send_json({"error": "Database not available"}, status=503)
            return

        try:
            with SessionLocal() as session:
                posts = session.query(SocialPost).order_by(SocialPost.id.desc()).all()
                data = []
                for p in posts:
                    data.append({
                        "id": p.id,
                        "platform": p.platform,
                        "post_id": p.post_id,
                        "title": p.title,
                        "author": p.author,
                        "content": p.content,
                        "score": p.score,
                        "num_comments": p.num_comments,
                        "url": p.url,
                        "post_created_at": p.post_created_at.isoformat() if p.post_created_at else None,
                        "inserted_at": p.inserted_at.isoformat() if p.inserted_at else None,
                        "raw_data": p.raw_data,
                    })
                self._send_json({"posts": data, "count": len(data)})
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def handle_api_run_pipeline(self):
        """Execute ETL pipeline synchronously and return updated counts."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            params = json.loads(body) if body else {}

            tag = params.get("tag", "python")
            limit = int(params.get("limit", 10))

            print(f"\n[DASHBOARD TRIGGER] Running ETL Pipeline (tag='{tag}', limit={limit})...")
            run_pipeline(tag=tag, limit=limit)

            # Return refreshed posts
            self.handle_api_posts()
        except Exception as e:
            self._send_json({"error": f"Pipeline execution failed: {str(e)}"}, status=500)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_server(port=8000, open_browser=True):
    server_address = ("", port)
    httpd = http.server.HTTPServer(server_address, ETLDashboardHandler)
    url = f"http://localhost:{port}"

    print("=" * 65)
    print(f"  SOCIAL MEDIA ETL DASHBOARD SERVER RUNNING")
    print(f"  URL: {url}")
    print(f"  PostgreSQL: {'Connected' if DB_AVAILABLE else 'Disabled/Not Found'}")
    print("=" * 65)
    print("Press Ctrl+C to stop the server.\n")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port=port, open_browser=False)
