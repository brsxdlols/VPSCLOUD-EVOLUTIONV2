import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('watchdog', ROOT / 'evolution-watchdog.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
spec = importlib.util.spec_from_file_location('enable_monitor', ROOT / 'evolution-enable-monitor.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        logger = patch.object(w.syslog, 'syslog')
        logger.start()
        self.addCleanup(logger.stop)
    def test_rate_limited_recovery(self):
        state = {}
        with patch.object(w, 'run', return_value=(0, '')) as run:
            w.attempt(state, 'docker_start', ['service', 'docker', 'start'], 1000)
            w.attempt(state, 'docker_start', ['service', 'docker', 'start'], 1100)
            self.assertEqual(run.call_count, 1)

    def test_no_restart_of_live_docker(self):
        def response(args, **kwargs):
            return (1, '') if args[0] == 'docker' else (0, '123')
        with patch.object(w, 'run', side_effect=response) as run:
            self.assertEqual(w.inspect_health({}, {}, 1000), ['DOCKER_INDISPONIVEL'])
            self.assertFalse(any('start' in call[0][0] or 'restart' in call[0][0] for call in run.call_args_list))

    def test_stopped_container_is_started_without_recreation(self):
        def response(args, **kwargs):
            if args[:2] == ['docker', 'info']:
                return 0, ''
            if args[:2] == ['docker', 'inspect']:
                return 0, 'false' if args[-1] == 'evolution_v2_api' else 'true'
            return 0, ''
        with patch.object(w, 'run', side_effect=response) as run:
            result = w.inspect_health({}, {}, 1000)
            self.assertEqual(result, ['CONTAINER_PARADO:evolution_v2_api'])
            self.assertTrue(any(call[0][0] == ['docker', 'start', 'evolution_v2_api'] for call in run.call_args_list))
            self.assertFalse(any('rm' in call[0][0] or 'restart' in call[0][0] for call in run.call_args_list))

    def test_second_failure_alerts_once_and_recovery_notifies(self):
        state = {}
        with patch.object(w, 'notify', return_value=True) as send:
            w.update_alerts({}, state, ['API_SEM_RESPOSTA'], 1000)
            self.assertEqual(send.call_count, 0)
            w.update_alerts({}, state, ['API_SEM_RESPOSTA'], 1060)
            w.update_alerts({}, state, ['API_SEM_RESPOSTA'], 1120)
            self.assertEqual(send.call_count, 1)
            w.update_alerts({}, state, [], 1180)
            self.assertEqual(send.call_count, 2)

    def test_instance_destination_and_no_false_recovery_when_docker_down(self):
        c = {'telegram_bot_token': 'global', 'telegram_chat_id': 'global-chat', 'instances': [{'name': 'MKAUTH', 'enabled': True, 'telegram_bot_token': 'specific', 'telegram_chat_id': 'specific-chat'}]}
        state = {}
        with patch.object(w, 'notify', return_value=True) as send:
            w.update_alerts(c, state, ['WHATSAPP_DESCONECTADO:MKAUTH'], 1000)
            w.update_alerts(c, state, ['WHATSAPP_DESCONECTADO:MKAUTH'], 1060)
            self.assertEqual(send.call_args[0][0]['telegram_chat_id'], 'specific-chat')
            w.update_alerts(c, state, ['DOCKER_INDISPONIVEL'], 1120)
            self.assertEqual(send.call_count, 1)

    def test_failed_delivery_retries(self):
        state = {}
        with patch.object(w, 'notify', return_value=False) as send:
            for now in [1000, 1060, 1120]:
                w.update_alerts({}, state, ['API_SEM_RESPOSTA'], now)
            self.assertEqual(send.call_count, 2)

    def test_number_survives_disconnection_and_docker_failure(self):
        config = {'instances': [{'name': 'MKAUTH', 'enabled': True}]}
        state = {'last_numbers': {'MKAUTH': {'number': '+5511999990000'}}}
        with patch.object(w, 'notify', return_value=True) as send:
            w.update_alerts(config, state, ['WHATSAPP_DESCONECTADO:MKAUTH'], 1000)
            w.update_alerts(config, state, ['WHATSAPP_DESCONECTADO:MKAUTH'], 1060)
            self.assertIn('Ultimo numero identificado: +5511999990000', send.call_args[0][1])
            w.update_alerts(config, state, ['DOCKER_INDISPONIVEL'], 1120)
            w.update_alerts(config, state, ['DOCKER_INDISPONIVEL'], 1180)
            self.assertIn('MKAUTH: +5511999990000', send.call_args[0][1])

    def test_health_probe_caches_registered_number(self):
        def response(args, **kwargs):
            if args[:2] == ['docker', 'info']:
                return 0, ''
            if args[:2] == ['docker', 'inspect']:
                return 0, 'true'
            return 0, json.dumps({'api': 200, 'instances': [{'name': 'MKAUTH', 'http': 200, 'state': 'close', 'phone': '+5511999990000'}]})
        state = {}
        with patch.object(w, 'run', side_effect=response):
            self.assertEqual(w.inspect_health({'instances': [{'name': 'MKAUTH', 'enabled': True}]}, state, 1000), ['WHATSAPP_DESCONECTADO:MKAUTH'])
            self.assertEqual(state['last_numbers']['MKAUTH']['number'], '+5511999990000')

    def test_photo_contains_caption_and_falls_back_to_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'assets').mkdir()
            (root / 'assets/critical.png').write_bytes(b'PNG-test-only')
            config = {'telegram_bot_token': 'fake-token', 'telegram_chat_id': '-100', '_alert_image': 'critical'}
            with patch.object(w, 'STATE_DIR', root), patch.object(w, 'telegram_request', return_value=True) as send:
                self.assertTrue(w.notify(config, 'Teste com numero +5511999990000'))
                self.assertEqual(send.call_args[0][1], 'sendPhoto')
                self.assertIn(b'+5511999990000', send.call_args[0][2])
                self.assertIn(b'PNG-test-only', send.call_args[0][2])
                self.assertEqual(send.call_count, 1)
            with patch.object(w, 'STATE_DIR', root), patch.object(w, 'telegram_request', side_effect=[False, True]) as send:
                self.assertTrue(w.notify(config, 'Alerta'))
                self.assertEqual([x[0][1] for x in send.call_args_list], ['sendPhoto', 'sendMessage'])

    def test_correct_photo_is_selected_and_recovery_scope_is_accurate(self):
        state = {}
        config = {'instances': [{'name': 'MKAUTH', 'enabled': True}]}
        with patch.object(w, 'notify', return_value=True) as send:
            w.update_alerts(config, state, ['WHATSAPP_DESCONECTADO:MKAUTH'], 1000)
            w.update_alerts(config, state, ['WHATSAPP_DESCONECTADO:MKAUTH'], 1060)
            self.assertEqual(send.call_args[0][0]['_alert_image'], 'whatsapp')
            w.update_alerts(config, state, [], 1120)
            self.assertEqual(send.call_args[0][0]['_alert_image'], 'recovery')
            self.assertIn('WhatsApp da instancia conectado', send.call_args[0][1])
            w.update_alerts(config, state, ['DOCKER_INDISPONIVEL'], 1180)
            w.update_alerts(config, state, ['DOCKER_INDISPONIVEL'], 1240)
            self.assertEqual(send.call_args[0][0]['_alert_image'], 'critical')

    def test_docker_recreation_preserves_port_mount_and_image(self):
        info = {'Image': 'sha256:existing', 'HostConfig': {'NetworkMode': 'evolution_v2_net', 'PortBindings': {'8080/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '7070'}]}}, 'Config': {'Entrypoint': ['/bin/bash', '-c', '. ./Docker/scripts/deploy_database.sh && npm run start:prod'], 'Cmd': None}, 'Mounts': [{'Type': 'bind', 'Source': '/existing/manager', 'Destination': '/evolution/manager/dist', 'RW': False}]}
        args = installer.recreate_args(info, Path('/backup/effective.env'))
        self.assertIn('0.0.0.0:7070:8080/tcp', args)
        self.assertIn('/existing/manager:/evolution/manager/dist:ro', args)
        self.assertEqual(args[-1], 'sha256:existing')
        info['HostConfig']['Privileged'] = True
        with self.assertRaises(ValueError):
            installer.recreate_args(info, Path('/backup/effective.env'))


if __name__ == '__main__':
    unittest.main()
