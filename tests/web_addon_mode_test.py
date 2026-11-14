from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BLOCK=(ROOT/'install-7070-replace-v1.sh').read_text().split('# WEB-ADDON-MODE-BEGIN\n')[1].split('# WEB-ADDON-MODE-END')[0]

@unittest.skipIf(os.name=='nt','POSIX shell fixture')
class WebAddonModeTests(unittest.TestCase):
    def execute(self,running='true',version='2.3.7'):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'admin').mkdir();calls=p/'calls';binary=p/'bin';binary.mkdir()
            scripts={'docker':'''#!/bin/sh
echo "$*" >> "$CALLS"
if [ "$1" = inspect ]; then echo "$RUNNING"; else echo "$VERSION"; fi
''','evolution-install-monitor':'#!/bin/sh\necho MONITOR >> "$CALLS"\n','evolution-install-web-addon':'#!/bin/sh\necho WEB_ADDON >> "$CALLS"\n'}
            for name,text in scripts.items():
                f=binary/name;f.write_text(text);f.chmod(0o755)
            source='API_CONTAINER=evolution_v2_api\ninstall_session_helpers(){ echo PREPARE >> "$CALLS"; }\n'+BLOCK.replace('/opt/mk-auth/admin',str(p/'admin')).replace('/usr/local/sbin',str(binary))
            script=p/'mode.sh';script.write_text('set -eu\n'+source)
            result=subprocess.run(['sh',str(script)],env=dict(os.environ,PATH=str(binary)+':'+os.environ['PATH'],EVOLUTION_MODE='web-addon',CALLS=str(calls),RUNNING=running,VERSION=version),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
            return result,calls.read_text() if calls.exists() else ''
    def test_only_prepares_monitor_and_addon_without_logout_or_upgrade(self):
        result,calls=self.execute();self.assertEqual(result.returncode,0,result.stdout)
        self.assertIn('PREPARE\nMONITOR\nWEB_ADDON',calls)
        self.assertNotIn('logout',calls);self.assertNotIn('pull',calls);self.assertNotIn('Pareamentos encerrados',result.stdout)
    def test_stopped_or_old_api_never_installs_helpers(self):
        for state,version in [('false','2.3.7'),('true','2.3.4')]:
            result,calls=self.execute(state,version);self.assertNotEqual(result.returncode,0)
            self.assertNotIn('PREPARE',calls)
