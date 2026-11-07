import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('key_monitor',ROOT/'evolution-enable-monitor.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class KeyConfigurationTests(unittest.TestCase):
    def test_validate_and_preserve_effective_environment(self):
        env=['AUTHENTICATION_API_KEY=old-key-123','DATABASE_PASSWORD=fake-db','NODE_OPTIONS=--trace-warnings']
        updated,old,new=m.key_env(env,'new-key-123');self.assertEqual(old,'old-key-123');self.assertEqual(new,'new-key-123');self.assertIn('DATABASE_PASSWORD=fake-db',updated);self.assertEqual(sum(x.startswith('AUTHENTICATION_API_KEY=') for x in updated),1)
        self.assertEqual(m.key_env(env,'')[2],old)
        with self.assertRaises(ValueError):m.key_env(env,'bad\nENV=1')
    def run_rotation(self,healthy=True,token='old-key-123'):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);monitor=root/'monitor';monitor.mkdir();receipt=root/'receipt.json';env=root/'evolution-v2.env'
        env.write_text('SERVER_URL=http://127.0.0.1:7070\nAUTHENTICATION_API_KEY=old-key-123\nDATABASE_PASSWORD=fake-db\n');os.chmod(str(env),0o600)
        receipt.write_text(json.dumps({'api_url':'http://127.0.0.1:7070','token':token,'receipts_enabled':False}));os.chmod(str(receipt),0o660)
        info={'State':{'Running':True},'Image':'sha256:existing','HostConfig':{'NetworkMode':'evolution_v2_net','PortBindings':{'8080/tcp':[{'HostIp':'0.0.0.0','HostPort':'7070'}]}},'Config':{'Env':['AUTHENTICATION_API_KEY=old-key-123','DATABASE_PASSWORD=fake-db'],'Entrypoint':['/bin/bash','-c','. ./Docker/scripts/deploy_database.sh && npm run start:prod'],'Cmd':None},'Mounts':[{'Type':'bind','Source':'/existing/manager','Destination':'/evolution/manager/dist','RW':False}]}
        calls=[]
        def command(args):
            calls.append(args)
            return json.dumps([info]) if args[:2]==['docker','inspect'] else 'fake-container-id'
        with patch.object(m,'PROJECT',root),patch.object(m,'MONITOR',monitor),patch.object(m,'RECEIPT',receipt),patch.object(m,'MAINTENANCE',root/'maintenance'),patch.object(m.os,'geteuid',return_value=0),patch.object(m,'command',side_effect=command),patch.object(m,'configure_docker_boot'),patch.object(m.sys,'argv',['helper','--key-only']),patch.dict(os.environ,{'EVOLUTION_API_KEY':'new-key-123'}),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0 if healthy else 1)),patch.object(m.time,'sleep'):
            if healthy:self.assertEqual(m.main(),0)
            else:
                with self.assertRaises(ValueError):m.main()
        return env,receipt,calls
    def test_rotation_preserves_data_and_syncs_matching_local_receipt(self):
        env,receipt,calls=self.run_rotation();self.assertIn('AUTHENTICATION_API_KEY=new-key-123',env.read_text());self.assertIn('DATABASE_PASSWORD=fake-db',env.read_text());self.assertEqual(json.loads(receipt.read_text())['token'],'new-key-123');self.assertEqual(receipt.stat().st_mode&0o777,0o660)
        runs=[x for x in calls if x[:2]==['docker','run']];self.assertEqual(len(runs),1);self.assertEqual(runs[0][-1],'sha256:existing');self.assertIn('/existing/manager:/evolution/manager/dist:ro',runs[0]);self.assertNotIn('/evolution/ops-monitor', ' '.join(runs[0]));self.assertFalse(any(x[1:3]==['volume','rm'] for x in calls))
    def test_unrelated_receipt_token_preserved(self):
        _,receipt,_=self.run_rotation(token='instance-key-456');self.assertEqual(json.loads(receipt.read_text())['token'],'instance-key-456')
    def test_failed_health_restores_previous_container_and_files(self):
        env,receipt,calls=self.run_rotation(False);self.assertIn('AUTHENTICATION_API_KEY=old-key-123',env.read_text());self.assertEqual(json.loads(receipt.read_text())['token'],'old-key-123');self.assertIn(['docker','start','evolution_v2_api'],calls);self.assertFalse(any('evolution_v2_postgres' in x or 'evolution_v2_redis' in x for x in calls))

if __name__=='__main__':unittest.main()
