import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('monitor',Path(__file__).resolve().parents[1]/'evolution-enable-monitor.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class StartupTests(unittest.TestCase):
    def test_slow_probe_is_retried_instead_of_rolling_back(self):
        with patch.object(m.subprocess,'run',side_effect=[subprocess.TimeoutExpired('probe',15),SimpleNamespace(returncode=0)]) as run,patch.object(m.time,'sleep'),patch.object(m.time,'monotonic',side_effect=range(100)):
            m.wait_monitor_ready('test');self.assertEqual(run.call_count,2)
    def test_failure_still_has_a_deadline(self):
        with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=1)),patch.object(m.time,'sleep'),patch.object(m.time,'monotonic',side_effect=[0,1,2,601]):
            with self.assertRaisesRegex(ValueError,'retomando container anterior'):m.wait_monitor_ready('test')
if __name__=='__main__':unittest.main()
