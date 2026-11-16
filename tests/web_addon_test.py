import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('web',ROOT/'evolution-install-web-addon.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)

class WebAddonTests(unittest.TestCase):
    def test_existing_shortcuts_move_to_options_without_duplicates(self):
        source="OTHER_ADDON();\n/* VPSCLOUD-RECIBO-BEGIN */\n;(function(){\n var item='receipt';\n if(typeof add_menu.financeiro==='function')add_menu.financeiro(item);\n if(typeof add_menu.provedor==='function')add_menu.provedor(item);\n})();\n/* VPSCLOUD-RECIBO-END */\n"
        one=w.menu(source,'172.16.30.25:7070')
        self.assertEqual(one,w.menu(one,'172.16.30.25:7070'))
        self.assertNotIn('add_menu.provedor',one)
        self.assertNotIn('add_menu.financeiro',one)
        self.assertEqual(one.count('add_menu.opcoes(item)'),1)
        self.assertEqual(one.count('add_menu.opcoes(JSON.stringify'),2)
        self.assertIn('OTHER_ADDON();',one)
    def test_detects_machine_address_and_actual_docker_port(self):
        info={'HostConfig':{'PortBindings':{'8080/tcp':[{'HostIp':'0.0.0.0','HostPort':'7070'}]}}}
        self.assertEqual(w.address(info,[{'prefsrc':'172.16.30.25'}]),('172.16.30.25:7070','7070'))
        with self.assertRaises(ValueError):w.address(info,[{'prefsrc':'127.0.0.1'}])
        info['HostConfig']['PortBindings']['8080/tcp'][0]['HostIp']='127.0.0.1'
        self.assertEqual(w.address(info,[]),('127.0.0.1:7070','7070'))
    def test_menu_update_is_idempotent_and_leaves_other_addons(self):
        source='OTHER_ADDON();\n';one=w.menu(source,'172.16.30.25:7070');two=w.menu(one,'172.16.30.25:7070')
        self.assertEqual(one,two);self.assertIn(source,one);self.assertEqual(one.count('VPSCLOUD-EVOLUTION-BEGIN'),1)
        self.assertIn('input[name="wapp_host"]',one);self.assertIn('Ver inst',one)
    def test_proxy_targets_only_loopback_and_preserves_addon_prefix(self):
        conf=w.apache('7070');self.assertIn('http://127.0.0.1:7070/admin/addons/evolution/app/',conf)
        self.assertIn('ws://127.0.0.1:7070/admin/addons/evolution/app/',conf)
        self.assertIn('ProxyPreserveHost On',conf)
        self.assertIn('ProxyPass "/admin/addons/evolution/ws/"',conf)
