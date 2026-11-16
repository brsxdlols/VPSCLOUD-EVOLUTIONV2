import os
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'install-7070-replace-v1.sh'
CODE=SOURCE.read_text().split("<<'IMAGE_ARCHIVE_CLEANUP'\n",1)[1].split('\nIMAGE_ARCHIVE_CLEANUP',1)[0]

class CleanupTests(unittest.TestCase):
    def test_removes_only_managed_images_and_updates_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project=root/'project';backups=project/'backups';backups.mkdir(parents=True)
            session=backups/'session-20261113-222219-26421';session.mkdir()
            (session/'api-image.tar').write_bytes(b'image')
            (session/'postgres.dump').write_bytes(b'database')
            manifest='a'*64+'  api-image.tar\n'+'b'*64+'  postgres.dump\n'
            (session/'SHA256SUMS').write_text(manifest)
            other=backups/'unmanaged';other.mkdir();(other/'api-image.tar').write_bytes(b'keep')
            code=CODE.replace("Path('/run/lock/vpscloud-evolution-session.lock')",repr(str(root/'lock')))
            # Keep lock operations on Path while using an isolated test directory.
            code=code.replace("lock="+repr(str(root/'lock')),"lock=Path("+repr(str(root/'lock'))+")")
            from unittest.mock import patch
            with patch.dict(os.environ,{'EVOLUTION_CLEANUP_PROJECT':str(project)}):
                exec(compile(code,'cleanup','exec'),{})
                exec(compile(code,'cleanup','exec'),{})
            self.assertFalse((session/'api-image.tar').exists())
            self.assertEqual((session/'postgres.dump').read_bytes(),b'database')
            self.assertEqual((session/'SHA256SUMS').read_text(),'b'*64+'  postgres.dump\n')
            self.assertEqual((session/'SHA256SUMS.before-image-cleanup').read_text(),manifest)
            self.assertTrue((other/'api-image.tar').exists())

if __name__=='__main__':unittest.main()
