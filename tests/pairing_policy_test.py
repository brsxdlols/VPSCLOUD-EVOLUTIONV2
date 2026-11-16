from pathlib import Path
import os,subprocess,unittest

ROOT=Path(__file__).resolve().parents[1]
BLOCK=(ROOT/'install-7070-replace-v1.sh').read_text().split('# PAIRING-POLICY-BEGIN\n')[1].split('# PAIRING-POLICY-END')[0]

@unittest.skipIf(os.name=='nt','POSIX shell fixture')
class PairingPolicyTests(unittest.TestCase):
    def run_policy(self,before,after,mode=None):
        env=dict(os.environ);env.pop('EVOLUTION_FORCE_RECONNECT',None)
        if mode is not None:env['EVOLUTION_FORCE_RECONNECT']=mode
        source='set -eu\nforce_existing_pairing_reset(){ echo REAL_LOGOUT_REQUEST; }\n'+BLOCK+'\napply_existing_pairing_policy "$1" "$2"\necho RESET=$PAIRINGS_RESET\n'
        return subprocess.run(['sh','-c',source,'fixture',before,after],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
    def test_current_version_preserves_pairing_on_repeated_runs(self):
        for _ in range(2):
            r=self.run_policy('2.3.7','2.3.7');self.assertEqual(r.returncode,0,r.stdout);self.assertNotIn('REAL_LOGOUT_REQUEST',r.stdout);self.assertIn('RESET=0',r.stdout)
    def test_actual_upgrade_still_requires_new_pairing(self):
        r=self.run_policy('2.3.4','2.3.7');self.assertEqual(r.returncode,0,r.stdout);self.assertEqual(r.stdout.count('REAL_LOGOUT_REQUEST'),1);self.assertIn('RESET=1',r.stdout)
    def test_explicit_operator_overrides(self):
        self.assertIn('REAL_LOGOUT_REQUEST',self.run_policy('2.3.7','2.3.7','1').stdout)
        self.assertNotIn('REAL_LOGOUT_REQUEST',self.run_policy('2.3.4','2.3.7','0').stdout)
    def test_invalid_final_version_or_mode_never_logs_out(self):
        for before,after,mode in [('2.3.7','2.3.4',None),('2.3.7','',None),('2.3.7','2.3.7','invalid')]:
            r=self.run_policy(before,after,mode);self.assertNotEqual(r.returncode,0);self.assertNotIn('REAL_LOGOUT_REQUEST',r.stdout)
