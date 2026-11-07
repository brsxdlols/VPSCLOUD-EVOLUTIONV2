import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('retire',Path(__file__).resolve().parents[1]/'evolution-retire-v1.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
        self.mount=self.root/'volume';self.mount.mkdir();(self.mount/'creds').write_text('fake-session')
        self.info={'Id':'old-id','Name':'/evolution_api','Image':'sha256:old','Config':{'Image':'atendai/evolution-api:v1.8.2','Env':[]},'State':{'Running':True},'Mounts':[{'Type':'volume','Name':'evolution_instances','Source':str(self.mount),'Destination':'/evolution/instances','RW':True}]}
    def test_identity_and_shared_volume_checks(self):
        self.assertEqual(m.plan(self.info,[])['volumes'],['evolution_instances'])
        other={'Mounts':copy.deepcopy(self.info['Mounts'])}
        with self.assertRaises(ValueError):m.plan(self.info,[other])
        wrong=copy.deepcopy(self.info);wrong['Config']['Image']='evoapicloud/evolution-api:v2.3.7'
        with self.assertRaises(ValueError):m.plan(wrong,[])
        wrong=copy.deepcopy(self.info);wrong['Mounts'][0]['Name']='evolution_v2_redis_data'
        with self.assertRaises(ValueError):m.plan(wrong,[])
    def test_latest_requires_confirmed_v1_package(self):
        item=copy.deepcopy(self.info);item['Config']['Image']='atendai/evolution-api:latest'
        with self.assertRaises(ValueError):m.plan(item,[])
        item['_legacy_version']='2.3.7'
        with self.assertRaises(ValueError):m.plan(item,[])
        item['_legacy_version']='1.8.2';self.assertEqual(m.plan(item,[])['id'],'old-id')
    def test_generic_host_bind_refused(self):
        item=copy.deepcopy(self.info);item['Mounts']=[{'Type':'bind','Source':'/opt/mk-auth','Destination':'/evolution','RW':True}]
        with self.assertRaises(ValueError):m.plan(item,[])
    def test_exclusive_bind_and_symlink_rules(self):
        legacy=self.root/'legacy';legacy.mkdir();instances=legacy/'instances';instances.mkdir()
        item=copy.deepcopy(self.info);item['Mounts']=[{'Type':'bind','Source':str(instances),'Destination':'/evolution/instances','RW':True}]
        with patch.object(m,'ROOTS',(legacy,)):
            self.assertEqual(m.plan(item,[])['roots'],[str(legacy)])
            with self.assertRaises(ValueError):m.plan(item,[{'Mounts':[{'Source':str(legacy/'config')}]}])
            link=legacy/'link';link.symlink_to(instances);item['Mounts'][0]['Source']=str(link)
            with self.assertRaises(ValueError):m.plan(item,[])
    def invoke(self,fail=False,others=None):
        others=others or []
        calls=[]
        def fake(*args):
            calls.append(args)
            if args[:2]==('image','inspect'):return json.dumps([{'Size':100}])
            if args[:2]==('inspect','--size'):return json.dumps([{'SizeRw':50}])
            if args[:2]==('image','save') or args[0]=='export':
                if fail:raise RuntimeError('fake backup failure')
                target=Path(args[args.index('-o')+1])
                with tarfile.open(str(target),'w') as t:
                    member=tarfile.TarInfo('fake');member.size=1;t.addfile(member,io.BytesIO(b'x'))
            return ''
        with patch.object(m,'BACKUPS',self.root/'backup'),patch.object(m,'docker',side_effect=fake),patch.object(m,'inventory',return_value=(self.info,others)),patch.object(m.shutil,'disk_usage',return_value=type('D',(),{'free':100*1024**3})()):
            if fail:
                with self.assertRaises(RuntimeError):m.retire(self.info,others)
            else:m.retire(self.info,others)
        return calls
    def test_backup_precedes_all_deletions(self):
        calls=self.invoke();self.assertLess(calls.index(('export','-o',next(c[2] for c in calls if c[0]=='export'),'evolution_api')),calls.index(('rm','evolution_api')))
        self.assertIn(('volume','rm','evolution_instances'),calls);self.assertIn(('image','rm','sha256:old'),calls)
        backup=next((self.root/'backup').iterdir());self.assertTrue((backup/'COMPLETE').exists());self.assertTrue((backup/'sha256.json').exists())
    def test_backup_failure_restarts_v1_without_deletion(self):
        calls=self.invoke(True);self.assertIn(('start','evolution_api'),calls);self.assertFalse(any(c[0]=='rm' or c[:2]==('volume','rm') for c in calls))
    def test_shared_image_is_not_deleted(self):
        calls=self.invoke(others=[{'Image':'sha256:old','Mounts':[]}])
        self.assertIn(('rm','evolution_api'),calls)
        self.assertNotIn(('image','rm','sha256:old'),calls)
    def test_shared_resources_abort_before_docker_mutation(self):
        with patch.object(m,'docker') as run:
            with self.assertRaises(ValueError):m.retire(self.info,[{'Mounts':self.info['Mounts']}])
            run.assert_not_called()
    def test_exclusive_legacy_folder_retired_into_backup(self):
        legacy=self.root/'legacy';legacy.mkdir();instances=legacy/'instances';instances.mkdir();(instances/'creds').write_text('fake')
        self.info['Mounts']=[{'Type':'bind','Source':str(instances),'Destination':'/evolution/instances','RW':True}]
        with patch.object(m,'ROOTS',(legacy,)):self.invoke()
        self.assertFalse(legacy.exists())
        backup=next((self.root/'backup').iterdir());self.assertEqual((backup/'retired-files/root-0/instances/creds').read_text(),'fake')

if __name__=='__main__':unittest.main()
