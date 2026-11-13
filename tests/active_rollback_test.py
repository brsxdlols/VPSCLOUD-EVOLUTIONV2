import copy
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'install-7070-replace-v1.sh').read_text().split("<<'RECOVER_ACTIVE_ROLLBACK'\n")[1].split('\nRECOVER_ACTIVE_ROLLBACK')[0]

class ActiveRollbackTests(unittest.TestCase):
    def exercise(self,change=None,multiple=False,rename_failure=False,already_running=False):
        ns={'__name__':'test'};exec(compile(SOURCE,'recovery','exec'),ns)
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        ns['PROJECT']=Path(tmp.name)
        old='evolution_v2_api_rollback_test'
        api={'State':{'Running':False},'Config':{'Image':'evoapicloud/evolution-api:v2.3.7','Env':['DATABASE_CONNECTION_URI=postgresql://fake','CACHE_REDIS_URI=redis://fake']},'HostConfig':{'NetworkMode':'evolution_v2_net','PortBindings':{'8080/tcp':[{'HostIp':'0.0.0.0','HostPort':'7070'}]}},'Mounts':[{'Type':'bind','Source':'/fixture/manager','Destination':'/evolution/manager/dist','RW':True}]}
        active=copy.deepcopy(api);active['State']['Running']=True;active['Config']['Image']='evoapicloud/evolution-api:v2.3.4'
        if change: change(active)
        if already_running:api['State']['Running']=True
        calls=[]
        def run(*args):
            calls.append(args)
            if args[:2]==('docker','ps'):return old+('\nevolution_v2_api_rollback_second' if multiple else '')
            if rename_failure and args[:3]==('docker','rename',old):raise RuntimeError('fake rename failure')
            return ''
        ns['run']=run;ns['inspect']=lambda name: api if name=='evolution_v2_api' else active
        return ns,calls

    def test_recovers_only_names_without_restarting_or_deleting(self):
        ns,calls=self.exercise();ns['main']()
        self.assertEqual(sum(x[:2]==('docker','rename') for x in calls),2)
        self.assertFalse(any(x[1] in ['start','stop','rm','exec','run'] for x in calls))
        self.assertEqual(len(list(ns['PROJECT'].glob('backups/*/containers.json'))),1)
        self.assertIn(('docker','update','--restart=no','evolution_v2_api'),calls)

    def test_multiple_candidates_are_rejected_before_mutation(self):
        ns,calls=self.exercise(multiple=True)
        with self.assertRaises(ValueError):ns['main']()
        self.assertFalse(any(x[1] in ['rename','update'] for x in calls))

    def test_different_backends_mounts_ports_or_network_are_rejected(self):
        changes=[lambda a:a['Config']['Env'].append('CACHE_REDIS_URI=redis://other'),lambda a:a['Mounts'][0].update(Source='/other'),lambda a:a['HostConfig'].update(NetworkMode='other'),lambda a:a['HostConfig']['PortBindings']['8080/tcp'][0].update(HostPort='8081')]
        for change in changes:
            ns,calls=self.exercise(change=change)
            with self.assertRaises(ValueError):ns['main']()
            self.assertFalse(any(x[1] in ['rename','update'] for x in calls))

    def test_rename_failure_restores_standard_name(self):
        ns,calls=self.exercise(rename_failure=True)
        with self.assertRaises(RuntimeError):ns['main']()
        saved=next(x[3] for x in calls if x[:3]==('docker','rename','evolution_v2_api'))
        self.assertEqual(calls[-1],('docker','rename',saved,'evolution_v2_api'))

    def test_running_standard_api_is_untouched(self):
        ns,calls=self.exercise(already_running=True);ns['main']();self.assertEqual(calls,[])
