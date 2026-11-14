import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('web',ROOT/'evolution-install-web-addon.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)

class WebAddonTests(unittest.TestCase):
    def test_detects_machine_address_and_actual_docker_port(self):
        info={'HostConfig':{'PortBindings':{'8080/tcp':[{'HostIp':'0.0.0.0','HostPort':'7070'}]}}}
        self.assertEqual(w.address(info,[{'prefsrc':'172.16.30.25'}]),('172.16.30.25:7070','7070'))
        with self.assertRaises(ValueError):w.address(info,[{'prefsrc':'127.0.0.1'}])
    def test_menu_update_is_idempotent_and_leaves_other_addons(self):
        source='OTHER_ADDON();\n';one=w.menu(source,'172.16.30.25:7070');two=w.menu(one,'172.16.30.25:7070')
        self.assertEqual(one,two);self.assertIn(source,one);self.assertEqual(one.count('VPSCLOUD-EVOLUTION-BEGIN'),1)
        self.assertIn('input[name="wapp_host"]',one);self.assertNotIn('wapp_pass',one)
    def test_proxy_targets_only_loopback_and_preserves_addon_prefix(self):
        conf=w.apache('7070');self.assertIn('http://127.0.0.1:7070/admin/addons/evolution/app/',conf)
        self.assertIn('ws://127.0.0.1:7070/admin/addons/evolution/app/',conf)
        self.assertIn('ProxyPreserveHost On',conf)
