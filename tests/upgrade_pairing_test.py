import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('upgrade', ROOT / 'evolution-upgrade-api.py')
u = importlib.util.module_from_spec(spec); spec.loader.exec_module(u)
spec = importlib.util.spec_from_file_location('pairing', ROOT / 'evolution-reset-pairing.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


class UpgradeTests(unittest.TestCase):
    def test_probe_uses_authenticated_api_and_installed_package_version(self):
        self.assertIn("require('/evolution/package.json')",u.PROBE)
        self.assertIn('/instance/fetchInstances',u.PROBE)
        self.assertNotIn("8080/'",u.PROBE)

    def fixture(self, stage_failure=False, production_failure=False, restore_failure=False, stop_failure=False):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name); folder = root / 'backups/session-test'; folder.mkdir(parents=True)
        monitor = root / 'monitor'; monitor.mkdir()
        (monitor / 'evolution-enable-monitor.py').write_text("def recreate_args(info,path,with_monitor=True): return ['docker','run','-d','--env-file',str(path),info['Image']]\n")
        (root / 'backups/LATEST-SESSION-BACKUP').write_text(str(folder))
        api = {'Id':'api-id','Name':'/'+u.API,'Image':'sha256:old','State':{'Running':True},'HostConfig':{'NetworkMode':'evolution_v2_net'},'Config':{'Env':['DATABASE_PROVIDER=postgresql','DATABASE_CONNECTION_URI=postgresql://evolution:fake@evolution_v2_postgres:5432/evolution_api','CACHE_REDIS_URI=redis://:fake@evolution_v2_redis:6379/6','AUTHENTICATION_API_KEY=fake-key']}}
        pg = {'Name':'/'+u.PG,'Image':'sha256:pg','State':{'Running':True},'Mounts':[{'Type':'volume','Destination':'/var/lib/postgresql/data','Name':'evolution_v2_postgres_data','Source':str(root/'pg')}]}
        redis = {'Name':'/'+u.REDIS,'Image':'sha256:redis','State':{'Running':True},'Mounts':[{'Type':'volume','Destination':'/data','Name':'evolution_v2_redis_data','Source':str(root/'redis')}]}
        target = {'Id':'sha256:new','Config':{'Entrypoint':['/bin/bash','-c','migrate && start'],'Cmd':None,'WorkingDir':'/evolution','User':''}}
        services = {u.API:api,u.PG:pg,u.REDIS:redis}; events = []
        def run(*args):
            events.append(args)
            if args[:3] == ('docker','image','inspect'): return json.dumps([target])
            if args[:3] == ('docker','ps','-aq'): return 'new-api-id'
            if args[:2] == ('docker','stop'):
                if stop_failure: raise ValueError('fake stop failure')
                api['State']['Running'] = False
            return ''
        def backup(*args, **kwargs):
            events.append(('BACKUP', kwargs.get('env',{}).get('EVOLUTION_BACKUP_KEEP_API_STOPPED')))
        def check(*args):
            events.append(('CHECK_BACKUP',))
        def stage(*args):
            events.append(('STAGE',))
            if stage_failure: raise ValueError('fake rehearsal failure')
        def restore_pg(*args):
            events.append(('RESTORE_PG',))
            if restore_failure: raise ValueError('fake restore failure')
        def restore_redis(*args): events.append(('RESTORE_REDIS',))
        with patch.object(u,'PROJECT',root), patch.object(u.os,'geteuid',return_value=0), patch.object(u,'inspect',side_effect=lambda n:services[n]), patch.object(u,'run',side_effect=run), patch.object(u,'probe',return_value={'version':'2.3.4','instances':[{'name':'FAKE'}]}), patch.object(u,'database_instances',return_value=[{'id':'fake-id','name':'FAKE'}]), patch.object(u,'check_capacity'), patch.object(u,'validate_exclusive_volumes'), patch.object(u.subprocess,'check_call',side_effect=backup), patch.object(u,'check_backup',side_effect=check), patch.object(u,'rehearsal',side_effect=stage), patch.object(u,'wait',side_effect=ValueError('fake production failure') if production_failure else None), patch.object(u,'restore_postgres',side_effect=restore_pg), patch.object(u,'restore_redis',side_effect=restore_redis):
            if stage_failure or production_failure:
                with self.assertRaises(ValueError): u.main()
            else: u.main()
        return folder, events

    def test_backup_and_rehearsal_precede_production(self):
        folder, events = self.fixture()
        self.assertLess(events.index(('BACKUP','1')),events.index(('STAGE',)))
        create = next(i for i,x in enumerate(events) if x[:2] == ('docker','run'))
        self.assertLess(events.index(('STAGE',)),create)
        self.assertTrue((folder/'UPGRADE-COMPLETE').exists())
        self.assertIn('sha256:new', events[create])

    def test_rehearsal_failure_restores_running_old_api_without_database_restore(self):
        _, events = self.fixture(stage_failure=True)
        self.assertIn(('docker','start',u.API),events)
        self.assertNotIn(('RESTORE_PG',),events)
        self.assertFalse(any(x[:2] == ('docker','run') for x in events))

    def test_failed_new_api_restores_both_databases_before_old_api_start(self):
        _, events = self.fixture(production_failure=True)
        self.assertLess(events.index(('RESTORE_PG',)),events.index(('RESTORE_REDIS',)))
        self.assertLess(events.index(('RESTORE_REDIS',)),events.index(('docker','start',u.API)))

    def test_failed_database_recovery_does_not_start_old_api(self):
        _, events = self.fixture(production_failure=True,restore_failure=True)
        self.assertNotIn(('docker','start',u.API),events)

    def test_running_failed_candidate_blocks_database_restore(self):
        _, events = self.fixture(production_failure=True,stop_failure=True)
        self.assertNotIn(('RESTORE_PG',),events)
        self.assertNotIn(('RESTORE_REDIS',),events)
        self.assertNotIn(('docker','start',u.API),events)

    def test_external_database_is_rejected(self):
        api={'Config':{'Env':['DATABASE_PROVIDER=postgresql','DATABASE_CONNECTION_URI=postgresql://evolution:fake@outside:5432/evolution_api','CACHE_REDIS_URI=redis://:fake@evolution_v2_redis:6379/6']}}
        with self.assertRaises(ValueError):u.validate_backends(api,{'Name':'/'+u.PG},{'Name':'/'+u.REDIS})

    def test_migration_rehearsal_uses_internal_network_and_only_its_resources(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);folder=Path(tmp.name);(folder/'before-upgrade.json').write_text(json.dumps({'instances':[],'database_instances':[]}))
        calls=[];token=['']
        info={'Config':{'Env':['DATABASE_CONNECTION_URI=postgresql://evolution:fake@old:5432/evolution_api','CACHE_REDIS_URI=redis://:fake@old:6379/6','NODE_OPTIONS=--require=/evolution/ops-monitor/monitor-hook.cjs']}}
        def fake(*args):
            calls.append(args)
            for a in args:
                if a.startswith('vpscloud.upgrade.check='): token[0]=a.split('=',1)[1]
            if args[:3] in [('docker','volume','inspect'),('docker','network','inspect')]:return json.dumps([{'Labels':{'vpscloud.upgrade.check':token[0]}}])
            return ''
        with patch.object(u,'run',side_effect=fake),patch.object(u,'inspect',side_effect=lambda n:{'Config':{'Labels':{'vpscloud.upgrade.check':token[0]}}}),patch.object(u,'restore_postgres'),patch.object(u,'wait'),patch.object(u,'database_instances',return_value=[]):
            u.rehearsal(folder,info,{'Image':'pg-image'},{'Image':'redis-image'},{'Id':'api-image'})
        network=next(x for x in calls if x[:3]==('docker','network','create'));self.assertIn('--internal',network)
        api_env=dict(x.split('=',1) for x in (folder/'rehearsal-api.env').read_text().splitlines())
        self.assertEqual(api_env['WEBHOOK_GLOBAL_ENABLED'],'false')
        self.assertNotIn('/evolution/ops-monitor',api_env['NODE_OPTIONS'])
        self.assertNotIn('old:5432',api_env['DATABASE_CONNECTION_URI'])
        for x in calls:
            if x[:2]==('docker','rm'):self.assertTrue(x[-1].startswith('evolution_upgrade_check_'))


class PairingTests(unittest.TestCase):
    def exercise(self,backup_failure=False,close=False):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);folder=root/'backups/session-test';folder.mkdir(parents=True);(root/'backups/LATEST-SESSION-BACKUP').write_text(str(folder))
        events=[];logged=[False]
        def api(method,path):
            events.append((method,path))
            if path=='/instance/fetchInstances':return {'http':200,'body':[{'name':'FAKE/name','integration':'WHATSAPP-BAILEYS','ownerJid':None if close else 'fake-owner'}]}
            if method=='DELETE':logged[0]=True;return {'http':200,'body':{}}
            if 'connectionState' in path:return {'http':200,'body':{'instance':{'state':'close' if close or logged[0] else 'open'}}}
            return {'http':200,'body':{}}
        def backup(*args,**kwargs):
            events.append(('BACKUP',))
            if backup_failure:raise RuntimeError('fake failure')
        with patch.object(p,'PROJECT',root),patch.object(p.os,'geteuid',return_value=0),patch.object(p,'api',side_effect=api),patch.object(p.subprocess,'check_call',side_effect=backup):
            if backup_failure:
                with self.assertRaises(RuntimeError):p.main()
            else:p.main()
        return events

    def test_logout_requires_backup_and_retains_instance(self):
        events=self.exercise();deletes=[e for e in events if e[0]=='DELETE']
        self.assertEqual(deletes,[('DELETE','/instance/logout/FAKE%2Fname')])
        self.assertLess(events.index(('BACKUP',)),events.index(deletes[0]))

    def test_backup_failure_never_logs_out(self):
        self.assertFalse(any(x[0]=='DELETE' for x in self.exercise(True)))

    def test_unpaired_closed_instance_is_not_deleted(self):
        self.assertFalse(any(x[0]=='DELETE' for x in self.exercise(close=True)))


if __name__=='__main__':unittest.main()

