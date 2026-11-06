import importlib.util
import json
from pathlib import Path
import unittest
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
