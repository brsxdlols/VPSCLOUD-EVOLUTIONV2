"""Only runs in an empty, disposable GitHub Actions runner. Never point it at a customer host."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path('/opt/vpscloud-evolution-v2')
NAMES = ['evolution_v2_api', 'evolution_v2_redis', 'evolution_v2_postgres']


def run(*args):
    return subprocess.check_output(list(args), stderr=subprocess.DEVNULL, universal_newlines=True, timeout=180).strip()


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('VPSCLOUD_CI_UPGRADE_TEST') != '1' or os.geteuid() != 0:
        raise ValueError('This test is restricted to a disposable GitHub Actions runner.')
    if PROJECT.exists() or run('docker', 'ps', '-aq'):
        raise ValueError('Runner is not empty. Nothing will be replaced.')
    PROJECT.mkdir(parents=True)
    (PROJECT / 'monitor').mkdir()
    shutil.copyfile(str(ROOT / 'evolution-enable-monitor.py'), str(PROJECT / 'monitor/evolution-enable-monitor.py'))
    helper = Path('/usr/local/sbin/evolution-backup')
    if helper.exists():
        raise ValueError('Backup helper already exists; refusing to overwrite it.')
    shutil.copyfile(str(ROOT / 'evolution-backup.sh'), str(helper))
    helper.chmod(0o700)
    spec = importlib.util.spec_from_file_location('live_upgrade', ROOT / 'evolution-upgrade-api.py')
    u = importlib.util.module_from_spec(spec); spec.loader.exec_module(u)
    networks, volumes, containers = [], [], []
    try:
        for image in ['postgres:15-alpine', 'redis:7.4-alpine', 'evoapicloud/evolution-api:v2.3.4', u.IMAGE]:
            run('docker', 'pull', image)
        run('docker', 'network', 'create', '--internal', 'evolution_v2_net'); networks.append('evolution_v2_net')
        for name in ['evolution_v2_postgres_data', 'evolution_v2_redis_data']:
            run('docker', 'volume', 'create', name); volumes.append(name)
        config = {
            'SERVER_TYPE': 'http', 'SERVER_PORT': '8080', 'SERVER_URL': 'http://127.0.0.1:7070',
            'AUTHENTICATION_API_KEY': 'ci-only-global-key', 'DATABASE_PROVIDER': 'postgresql',
            'DATABASE_CONNECTION_URI': 'postgresql://evolution:ci-only-db@evolution_v2_postgres:5432/evolution_api?schema=public',
            'DATABASE_CONNECTION_CLIENT_NAME': 'ci_upgrade', 'DATABASE_PASSWORD': 'ci-only-db',
            'CACHE_REDIS_ENABLED': 'true', 'CACHE_REDIS_SAVE_INSTANCES': 'true',
            'CACHE_REDIS_URI': 'redis://:ci-only-redis@evolution_v2_redis:6379/6',
            'CACHE_REDIS_PREFIX_KEY': 'ci-upgrade', 'CACHE_LOCAL_ENABLED': 'false',
            'LOG_LEVEL': 'ERROR,WARN,INFO,LOG,DEBUG', 'LOG_BAILEYS': 'error', 'WEBHOOK_GLOBAL_ENABLED': 'false',
            'DATABASE_SAVE_DATA_INSTANCE': 'true', 'DATABASE_SAVE_DATA_NEW_MESSAGE': 'true',
            'DATABASE_SAVE_DATA_CONTACTS': 'true', 'DATABASE_SAVE_DATA_CHATS': 'true',
            'DATABASE_SAVE_DATA_HISTORIC': 'true', 'DATABASE_SAVE_MESSAGE_UPDATE': 'false',
        }
        u.write_env(PROJECT / 'evolution-v2.env', config)
        containers.append(NAMES[2])
        run('docker', 'run', '-d', '--name', NAMES[2], '--network', 'evolution_v2_net',
            '-e', 'POSTGRES_USER=evolution', '-e', 'POSTGRES_PASSWORD=ci-only-db', '-e', 'POSTGRES_DB=evolution_api',
            '-v', volumes[0] + ':/var/lib/postgresql/data', 'postgres:15-alpine')
        containers.append(NAMES[1])
        run('docker', 'run', '-d', '--name', NAMES[1], '--network', 'evolution_v2_net',
            '-v', volumes[1] + ':/data', 'redis:7.4-alpine', 'redis-server', '--appendonly', 'yes', '--requirepass', 'ci-only-redis')
        for _ in range(60):
            try:
                run('docker', 'exec', NAMES[2], 'pg_isready', '-h', '127.0.0.1', '-U', 'evolution', '-d', 'evolution_api')
                run('docker', 'exec', '-e', 'REDISCLI_AUTH=ci-only-redis', NAMES[1], 'redis-cli', 'PING')
                break
            except Exception:
                time.sleep(1)
        containers.append(NAMES[0])
        print('Starting isolated 2.3.4 fixture', flush=True)
        run('docker', 'run', '-d', '--name', NAMES[0], '--network', 'evolution_v2_net',
            '--env-file', str(PROJECT / 'evolution-v2.env'), '-p', '127.0.0.1:7070:8080',
            'evoapicloud/evolution-api:v2.3.4')
        u.wait(NAMES[0], '2.3.4')
        create = """(async()=>{const r=await fetch('http://127.0.0.1:8080/instance/create',{method:'POST',headers:{apikey:process.env.AUTHENTICATION_API_KEY,'Content-Type':'application/json'},body:JSON.stringify({instanceName:'CI_ONLY_NO_PHONE',integration:'WHATSAPP-BAILEYS',qrcode:false})});if(!r.ok)process.exit(1)})().catch(()=>process.exit(1))"""
        run('docker', 'exec', NAMES[0], 'node', '-e', create)
        original = u.database_instances(NAMES[2])
        if len(original) != 1:
            raise ValueError('Fixture instance was not created.')
        run('docker', 'exec', '-e', 'REDISCLI_AUTH=ci-only-redis', NAMES[1], 'redis-cli', '-n', '6', 'SET', 'ci:upgrade:sentinel', 'keep-me')
        actual_wait = u.wait

        def failed_production(name, version=None, expected=None):
            if name == NAMES[0] and version == '2.3.7':
                actual_wait(name, version, expected)
                raise ValueError('Injected failure after real production migrations.')
            return actual_wait(name, version, expected)

        with patch.object(u, 'wait', side_effect=failed_production):
            try:
                u.main()
            except ValueError as error:
                if 'Injected failure' not in str(error):
                    raise
            else:
                raise ValueError('Failure injection did not execute.')
        u.wait(NAMES[0], '2.3.4')
        if u.database_instances(NAMES[2]) != original:
            raise ValueError('Rollback did not restore instance IDs.')
        if run('docker', 'exec', '-e', 'REDISCLI_AUTH=ci-only-redis', NAMES[1], 'redis-cli', '-n', '6', 'GET', 'ci:upgrade:sentinel') != 'keep-me':
            raise ValueError('Rollback did not restore Redis.')
        print('PASS real PostgreSQL + Redis rollback after injected post-migration failure')
        u.main()
        u.wait(NAMES[0], '2.3.7')
        if u.database_instances(NAMES[2]) != original:
            raise ValueError('Successful upgrade did not preserve instance IDs.')
        if run('docker', 'exec', '-e', 'REDISCLI_AUTH=ci-only-redis', NAMES[1], 'redis-cli', '-n', '6', 'GET', 'ci:upgrade:sentinel') != 'keep-me':
            raise ValueError('Successful upgrade changed the Redis fixture.')
        print('PASS real 2.3.4 -> 2.3.7 upgrade preserves instance ID and Redis sentinel')
    except Exception:
        try:
            print(run('docker', 'exec', NAMES[0], 'node', '-e', "(async()=>{for(const p of ['/', '/instance/fetchInstances']){try{const r=await fetch('http://127.0.0.1:8080'+p,{headers:{apikey:process.env.AUTHENTICATION_API_KEY},signal:AbortSignal.timeout(3000)});console.log(p,r.status,await r.text())}catch(e){console.log(p,e.message)}}})()"))
            print(run('docker', 'exec', NAMES[0], 'ps', '-ef'))
        except Exception:
            pass
        for file in (PROJECT / 'backups').glob('*/*.private.log'):
            print('Isolated fixture logs: ' + file.name)
            print(file.read_text(errors='replace')[-12000:])
        for name in containers:
            try:
                print('Fixture logs: ' + name)
                print(subprocess.check_output(['docker','logs','--tail','150',name],stderr=subprocess.STDOUT,universal_newlines=True,timeout=30))
            except Exception:
                pass
        raise
    finally:
        # This VM started empty; remove only fixture names/prefixes it created.
        for name in run('docker', 'ps', '-a', '--format', '{{.Names}}').splitlines():
            if name in containers or name.startswith(('evolution_v2_api_before_', 'evolution_v2_api_upgrade_failed_', 'evolution_upgrade_')):
                try: run('docker', 'rm', '-f', name)
                except Exception: pass
        for name in volumes:
            try: run('docker', 'volume', 'rm', name)
            except Exception: pass
        for name in networks:
            try: run('docker', 'network', 'rm', name)
            except Exception: pass


if __name__ == '__main__':
    main()

