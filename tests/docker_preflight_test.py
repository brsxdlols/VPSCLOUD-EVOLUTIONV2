import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
CODE=(ROOT/'install-7070-replace-v1.sh').read_text().split("<<'DOCKER_PREFLIGHT'\n",1)[1].split('\nDOCKER_PREFLIGHT',1)[0]
class DockerPreflightTests(unittest.TestCase):
    def execute(self,replies,systemd=True,env=None):
        calls=[]
        def run(args,**kwargs):calls.append(args);return subprocess.CompletedProcess(args,replies.pop(0))
        with patch('subprocess.run',side_effect=run),patch('time.sleep'),patch.object(Path,'is_dir',return_value=systemd),patch.object(Path,'is_file',return_value=True),patch.dict(os.environ,{'DOCKER_HOST':'','DOCKER_CONTEXT':'default',**(env or {})}):
            with self.assertRaises(SystemExit) as e:exec(compile(CODE,'preflight','exec'),{})
        return e.exception.code,calls
    def test_healthy_docker_does_not_start_service(self):
        code,calls=self.execute([0]);self.assertEqual(code,0);self.assertEqual(len(calls),1)
    def test_stopped_docker_is_started_and_rechecked(self):
        code,calls=self.execute([1,1,0,0]);self.assertEqual(code,0);self.assertIn(['systemctl','start','docker'],calls)
    def test_sysv_service_supported(self):
        code,calls=self.execute([1,1,0,0],systemd=False);self.assertEqual(code,0);self.assertIn(['/etc/init.d/docker','start'],calls)
    def test_live_but_unresponsive_docker_is_not_restarted(self):
        code,calls=self.execute([1,0]+[1]*6);self.assertIn('continua indisponivel',code);self.assertFalse(any('start' in c or 'restart' in c for c in calls))
    def test_failed_service_start_aborts(self):
        code,calls=self.execute([1,1,1]+[1]*6);self.assertIn('continua indisponivel',code)
    def test_remote_docker_never_starts_local_service(self):
        code,calls=self.execute([1],env={'DOCKER_HOST':'tcp://remote:2376'});self.assertIn('remoto',code);self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main()
