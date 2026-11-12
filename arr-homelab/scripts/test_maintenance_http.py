"""Exercise both real urllib request paths against a local HTTP server."""
import http.cookiejar
import importlib.util
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import urllib.parse
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('maintenance', Path(__file__).with_name('arr-maintenance.py'))
maintenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintenance)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, payload, cookie=False):
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        if cookie:
            self.send_header('Set-Cookie', 'testSession=present; Path=/')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == '/api/v2/app/preferences' and self.headers.get('Cookie') != 'testSession=present':
            self.send_response(403)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.reply({'cookie': self.headers.get('Cookie')}, cookie=True)

    def do_POST(self):
        if self.path == '/api/v2/auth/login':
            self.server.login_body = urllib.parse.parse_qs(
                self.rfile.read(int(self.headers['Content-Length'])).decode())
            accepted = self.server.login_body == {
                'username': ['admin'], 'password': ['test-managed-password']}
            status = getattr(self.server, 'login_status', 200) if accepted else 200
            raw = (b'' if status == 204 else b'Ok.') if accepted else b'Fails.'
            self.send_response(status)
            self.send_header('Content-Length', str(len(raw)))
            if accepted and getattr(self.server, 'include_login_cookie', True):
                self.send_header('Set-Cookie', 'testSession=present; Path=/')
            self.end_headers()
            self.wfile.write(raw)
            return
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.reply({'body': body, 'method': 'POST'})


class HttpIntegrationTest(unittest.TestCase):
    def test_managed_downloader_login_and_session(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            for status in (200, 204):
                with self.subTest(login_status=status):
                    server.login_status = status
                    with patch.object(maintenance, 'secret', return_value='test-managed-password') as secret:
                        endpoint, opener = maintenance.qbittorrent(base)
                        secret.assert_called_once_with('QBITTORRENT_WEBUI_PASSWORD')
                    self.assertEqual(endpoint, base)
                    self.assertEqual(maintenance.http(base, opener=opener),
                                     {'cookie': 'testSession=present'})
            with patch.object(maintenance, 'secret', return_value='incorrect-password'):
                with self.assertRaisesRegex(RuntimeError, 'authentication rejected'):
                    maintenance.qbittorrent(base)
            server.login_status = 204
            server.include_login_cookie = False
            with patch.object(maintenance, 'secret', return_value='test-managed-password'):
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    maintenance.qbittorrent(base)
                self.assertEqual(rejected.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_plain_post_and_cookie_opener(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            self.assertEqual(maintenance.http(base), {'cookie': None})
            self.assertEqual(maintenance.http(base, 'POST', {'port': 12345}),
                             {'body': {'port': 12345}, 'method': 'POST'})
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            maintenance.http(base, opener=opener)
            self.assertEqual(maintenance.http(base, opener=opener), {'cookie': 'testSession=present'})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
