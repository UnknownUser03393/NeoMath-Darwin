#!/usr/bin/env python3
"""Expose the existing local backend to an iPad on the same private LAN."""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Proxy(BaseHTTPRequestHandler):
    def forward(self):
        if not (self.path == '/api' or self.path.startswith('/api/')):
            self.send_error(404)
            return
        upstream = http.client.HTTPConnection('127.0.0.1', 8765, timeout=30)
        try:
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            upstream.request(self.command, self.path, body, {'Content-Type': self.headers.get('Content-Type', 'application/json')})
            reply = upstream.getresponse()
            data = reply.read()
            self.send_response(reply.status)
            self.send_header('Content-Type', reply.getheader('Content-Type', 'application/json'))
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (OSError, http.client.HTTPException):
            self.send_error(502, 'Local NeoMath backend unavailable')
        finally:
            upstream.close()
    do_GET = forward
    do_POST = forward

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), Proxy).serve_forever()
