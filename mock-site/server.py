#!/usr/bin/env python3
"""
Simple HTTP server to serve the mock university site.
Run this instead of the Nginx docker container if Docker is not available.
"""
import http.server
import socketserver
import os
from pathlib import Path

PORT = 8080
DIRECTORY = Path(__file__).parent.absolute()

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Mock Site serving at port {PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
