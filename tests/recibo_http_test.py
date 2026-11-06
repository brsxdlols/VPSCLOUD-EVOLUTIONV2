"""Real-test endpoint against a loopback fake Evolution API; no customer/queue DB."""
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]

class ReceiptHTTPTest(unittest.TestCase):
    def test_only_explicit_test_destination_and_fake_data_are_sent(self):
        calls = []
        class FakeAPI(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def reply(self, value):
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps(value).encode())
            def do_GET(self):
                calls.append(('GET', self.path, None)); self.reply({'instance': {'state': 'open'}})
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append(('POST', self.path, body)); self.reply({'key': {'id': 'fake-message-id'}})
        fake = http.server.HTTPServer(('127.0.0.1', 0), FakeAPI)
        thread = threading.Thread(target=fake.serve_forever, daemon=True); thread.start()
        with tempfile.TemporaryDirectory(prefix='recibo-http-test-') as tmp:
            folder = Path(tmp); data = folder / 'data'; data.mkdir()
            for name in ['common.php', 'api.php']:
                shutil.copyfile(ROOT / 'addon/Recibo_Evolution' / name, folder / name)
            (folder / 'addons.class.php').write_text("<?php session_name('receipt_mock');session_start();$_SESSION['MKA_Logado']=true;$_SESSION['recibo_csrf']='unit-csrf';", encoding='utf8')
            (data / 'settings.json').write_text(json.dumps({'api_url': 'http://127.0.0.1:%s' % fake.server_port, 'instance': 'TEST_ONLY', 'token': 'mock-token', 'provider': 'Example', 'template': '{cliente} {id_pagamento} {valor_pago}'}))
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            env = dict(os.environ, RECIBO_DATA_DIR=str(data))
            php = subprocess.Popen(['php', '-d', 'session.save_path='+str(folder), '-S', '127.0.0.1:%s' % port, '-t', str(folder)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.1): break
                    except OSError: time.sleep(.03)
                def request(body):
                    req = urllib.request.Request('http://127.0.0.1:%s/api.php' % port, data=body.encode(), headers={'Cookie': 'receipt_mock=testsession', 'Content-Type': 'application/x-www-form-urlencoded'})
                    try: response = urllib.request.urlopen(req, timeout=10)
                    except urllib.error.HTTPError as err: response = err
                    return response.status, json.loads(response.read())
                status, result = request('action=send_test&csrf=unit-csrf&test_phone=11999990000')
                self.assertEqual(status, 400); self.assertEqual(calls, [])
                status, result = request('action=send_test&csrf=unit-csrf&confirm_test=ENVIAR_TESTE&test_phone=11999990000')
                self.assertEqual(status, 200); self.assertIn('aceito', result['message'])
                self.assertEqual(len(calls), 2); self.assertEqual(calls[1][2]['number'], '5511999990000')
                self.assertIn('TESTE', calls[1][2]['text']); self.assertIn('Cliente de exemplo', calls[1][2]['text'])
                self.assertFalse((data / 'database.php').exists())
                status, result = request('action=send_test&csrf=unit-csrf&confirm_test=ENVIAR_TESTE&test_phone=11999990000')
                self.assertEqual(status, 400); self.assertEqual(len(calls), 2)
                status, result = request('action=send_test&csrf=invalid&confirm_test=ENVIAR_TESTE&test_phone=11999990000')
                self.assertEqual(status, 403); self.assertEqual(len(calls), 2)
            finally:
                php.terminate(); php.wait(timeout=5); fake.shutdown(); fake.server_close(); thread.join(timeout=2)

if __name__ == '__main__':
    unittest.main()
