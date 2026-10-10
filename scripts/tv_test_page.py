#!/usr/bin/env python3
"""Owner-run loopback-only TV test page; no local files or media are served.

The TV fetches public media URLs directly, so localhost is never handed to it.
No logging of request paths, browser information, PINs or receiver state.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse

PAGE = b'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>PearPlay TV test</title><style>body{font:18px/1.5 system-ui;max-width:850px;padding:30px;margin:auto;background:#111914;color:#f4f7ed}button{font:inherit;padding:12px;margin:8px;border:1px solid #a5ba91;border-radius:8px;background:#c1e67a;color:#172310}video{display:block;width:100%;max-height:440px;background:#000}a{color:#c1e67a}#status{min-height:3em}</style><h1>PearPlay TV test</h1><p>Select a sample, open PearPlay, find videos and choose your TV. Press Send to TV only when you are ready to watch and listen.</p><button id="mp4">1. MP4 sample</button><button id="hls">2. HLS sample</button><p id="status" role="status">MP4 selected. Play it here first, then open PearPlay.</p><video controls preload="metadata" title="PearPlay public MP4 sample" src="https://media.w3.org/2010/05/bunny/trailer.mp4"></video><p>The HLS sample may not play in Chrome itself. It still exposes the exact public playlist to PearPlay; click Find videos after changing samples. A TV buffering spinner is not a pass.</p><p>No login or payment. These sample providers and the TV use the network. This page is served only to this computer; it does not collect test results.</p><script>const video=document.querySelector('video');function select(kind){video.pause();video.src=kind==='mp4'?'https://media.w3.org/2010/05/bunny/trailer.mp4':'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8';video.title='PearPlay public '+kind.toUpperCase()+' sample';video.load();document.querySelector('#status').textContent=kind.toUpperCase()+' selected. Click Find videos in PearPlay again; choose the new sample before sending.'}document.querySelector('#mp4').onclick=()=>select('mp4');document.querySelector('#hls').onclick=()=>select('hls');</script></html>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/', '/index.html'):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(PAGE)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose a port from 1024 to 65535.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Open http://127.0.0.1:{args.port}/ in Chrome. Ctrl+C stops this test page.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
