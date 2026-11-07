import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import time
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/'install-7070-replace-v1.sh').read_text()
FUNCTION=SOURCE[SOURCE.index('choose_api_key() {'):SOURCE.index('create_env() {')]
class KeyPromptTests(unittest.TestCase):
    def run_prompt(self,current,typed):
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'key.sh';script.write_text('set -eu\n'+FUNCTION+'\nchoose_api_key "$CURRENT"\nprintf "RESULT=%s\\n" "$API_KEY"\n')
            master,slave=pty.openpty();env=dict(os.environ,CURRENT=current);env.pop('EVOLUTION_API_KEY',None)
            process=subprocess.Popen(['sh',str(script)],stdin=slave,stdout=slave,stderr=slave,env=env);os.close(slave);out=b'';sent=False;deadline=time.time()+5
            try:
                while time.time()<deadline:
                    if select.select([master],[],[],.1)[0]:
                        try:chunk=os.read(master,4096)
                        except OSError:break
                        if not chunk:break
                        out+=chunk
                        if not sent and b'visivel' in out:os.write(master,typed.encode()+b'\n');sent=True
                    if process.poll() is not None and not select.select([master],[],[],.1)[0]:break
                process.wait(timeout=2)
            finally:
                os.close(master)
                if process.poll() is None:process.kill();process.wait()
            return process.returncode,out.decode()
    def test_new_install_visible_prompt_accepts_choice(self):
        code,out=self.run_prompt('','chosen-key-123');self.assertEqual(code,0);self.assertIn('RESULT=chosen-key-123',out);self.assertIn('texto visivel',out)
    def test_existing_install_enter_keeps_key(self):
        code,out=self.run_prompt('existing-key-123','');self.assertEqual(code,0);self.assertIn('RESULT=existing-key-123',out)
    def test_existing_install_accepts_replacement(self):
        code,out=self.run_prompt('existing-key-123','replacement-456');self.assertEqual(code,0);self.assertIn('RESULT=replacement-456',out)
    def test_new_install_enter_generates_key(self):
        import re
        code,out=self.run_prompt('','');self.assertEqual(code,0);self.assertIsNotNone(re.search(r'RESULT=[a-f0-9]{64}',out))
    def test_invalid_key_rejected(self):
        code,_=self.run_prompt('','bad key');self.assertNotEqual(code,0)

if __name__=='__main__':unittest.main()
