#!/usr/bin/env python3
"""Upgrade the supported standard deployment without reusing migrated data on rollback."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid

PROJECT = Path('/opt/vpscloud-evolution-v2')
API = 'evolution_v2_api'
PG = 'evolution_v2_postgres'
REDIS = 'evolution_v2_redis'
IMAGE = 'evoapicloud/evolution-api@sha256:1bd8afc4a6cf48822e6cf02469aeae7bd35a12a6b616eacd1291926307f4d339'
BACKUP_HELPER = '/usr/local/sbin/evolution-backup'
PROBE = """(async()=>{let r=await fetch('http://127.0.0.1:8080/',{signal:AbortSignal.timeout(4000)});if(!r.ok)process.exit(1);let v=await r.json();let q=await fetch('http://127.0.0.1:8080/instance/fetchInstances',{headers:{apikey:process.env.AUTHENTICATION_API_KEY},signal:AbortSignal.timeout(4000)});if(!q.ok)process.exit(1);let a=await q.json();if(!Array.isArray(a))process.exit(1);console.log(JSON.stringify({version:v.version,instances:a.map(x=>({name:x.name||x.instance?.instanceName||x.instanceName})).sort((a,b)=>a.name.localeCompare(b.name))}))})().catch(()=>process.exit(1))"""


def run(*args):
    return subprocess.check_output(list(args), stderr=subprocess.DEVNULL, universal_newlines=True).strip()


def inspect(name):
    return json.loads(run('docker', 'inspect', name))[0]


def environment(info):
    return dict(x.split('=', 1) for x in info['Config'].get('Env', []) if '=' in x)


def probe(name):
    return json.loads(run('docker', 'exec', name, 'node', '-e', PROBE))


def wait(name, version=None, expected=None):
    for _ in range(60):
        try:
            result = probe(name)
            if (not version or str(result['version']).lstrip('v') == version) and (expected is None or result['instances'] == expected):
                return result
        except Exception:
            pass
        time.sleep(2)
    raise ValueError('API nao validou versao, autenticacao e instancias no prazo.')


def write_env(path, values):
    if any('\n' in v or '\r' in v for v in values.values()):
        raise ValueError('ENV multiline nao suportado.')
    path.write_text(''.join(k + '=' + v + '\n' for k, v in values.items()))
    os.chmod(str(path), 0o600)


def volume(info, destination):
    entries = [m for m in info['Mounts'] if m['Destination'] == destination and m['Type'] == 'volume']
    if len(entries) != 1:
        raise ValueError('Volume persistente nao padrao; atualizacao abortada.')
    return entries[0]


def validate_backends(info, pg, redis):
    values = environment(info)
    for field, service, port, path in [('DATABASE_CONNECTION_URI', pg, 5432, '/evolution_api'), ('CACHE_REDIS_URI', redis, 6379, '/6')]:
        uri = urllib.parse.urlsplit(values.get(field, ''))
        network = service.get('NetworkSettings', {}).get('Networks', {}).get('evolution_v2_net', {})
        aliases = set(network.get('Aliases') or []) | {service.get('Name', '').lstrip('/'), network.get('IPAddress', '')}
        if uri.hostname not in aliases or uri.path != path or (uri.port or port) != port:
            raise ValueError('Backend da API difere dos bancos locais; atualizacao automatica bloqueada.')
    if values.get('DATABASE_PROVIDER') != 'postgresql':
        raise ValueError('Provider de banco nao suportado para atualizacao automatica.')


def check_backup(folder):
    subprocess.check_call(['sha256sum', '-c', 'SHA256SUMS'], cwd=str(folder), stdout=subprocess.DEVNULL)
    for name in ['postgres.dump', 'redis.rdb', 'containers.json', 'api-image.tar']:
        if not (folder / name).is_file() or not (folder / name).stat().st_size:
            raise ValueError('Backup incompleto; atualizacao abortada.')


def database_instances(name):
    value = run('docker', 'exec', name, 'psql', '-U', 'evolution', '-d', 'evolution_api', '-tA', '-v', 'ON_ERROR_STOP=1', '-c', 'SELECT COALESCE(json_agg(q),\'[]\'::json) FROM (SELECT id,name FROM "Instance" ORDER BY id) q')
    return json.loads(value)


def check_capacity(pg, redis):
    size = 0
    for service, destination in [(pg, '/var/lib/postgresql/data'), (redis, '/data')]:
        source = volume(service, destination)['Source']
        used = int(run('du', '-sk', '--apparent-size', source).split()[0]) * 1024
        if shutil.disk_usage(source).free < used * 2 + 1024 ** 3:
            raise ValueError('Espaco insuficiente no Docker para validar a copia isolada.')
        size += used
    if shutil.disk_usage(str(PROJECT)).free < 4 * 1024 ** 3 + size * 3:
        raise ValueError('Espaco insuficiente para backups e validacao da atualizacao; API preservada.')


def validate_exclusive_volumes(pg, redis):
    ids = run('docker', 'ps', '-q').split()
    others = json.loads(run('docker', 'inspect', *ids)) if ids else []
    sources = [Path(volume(pg, '/var/lib/postgresql/data')['Source']), Path(volume(redis, '/data')['Source'])]
    for item in others:
        if item.get('Name', '').lstrip('/') in (API, PG, REDIS):
            continue
        for mount in item.get('Mounts', []):
            other = Path(mount.get('Source', '/unrelated'))
            if any(other == source or other in source.parents or source in other.parents for source in sources):
                raise ValueError('Banco compartilhado com outro container; atualizacao automatica bloqueada.')


def restore_postgres(folder, name):
    target = '/tmp/vpscloud-upgrade-restore.dump'
    run('docker', 'cp', str(folder / 'postgres.dump'), name + ':' + target)
    run('docker', 'exec', name, 'psql', '-U', 'evolution', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1',
        '-c', "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='evolution_api' AND pid<>pg_backend_pid()")
    run('docker', 'exec', name, 'psql', '-U', 'evolution', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-c', 'DROP DATABASE IF EXISTS evolution_api')
    run('docker', 'exec', name, 'psql', '-U', 'evolution', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-c', 'CREATE DATABASE evolution_api OWNER evolution')
    run('docker', 'exec', name, 'pg_restore', '-U', 'evolution', '-d', 'evolution_api', '--exit-on-error', target)
    run('docker', 'exec', name, 'rm', '-f', target)


def rehearsal(folder, info, pg, redis, target):
    token = uuid.uuid4().hex
    prefix = 'evolution_upgrade_check_' + token[:12]
    network, pv, rv, pn, rn, an = [prefix + x for x in ['_net', '_pgdata', '_redisdata', '_pg', '_redis', '_api']]
    created, volumes, net = [], [], False
    try:
        run('docker', 'network', 'create', '--internal', '--label', 'vpscloud.upgrade.check=' + token, network)
        net = True
        for name in [pv, rv]:
            run('docker', 'volume', 'create', '--label', 'vpscloud.upgrade.check=' + token, name)
            volumes.append(name)
        password = uuid.uuid4().hex
        pg_env = folder / 'rehearsal-postgres.env'
        write_env(pg_env, {'POSTGRES_USER': 'evolution', 'POSTGRES_PASSWORD': password, 'POSTGRES_DB': 'evolution_api'})
        created.append(pn)
        run('docker', 'run', '-d', '--name', pn, '--network', network, '--label', 'vpscloud.upgrade.check=' + token,
            '--env-file', str(pg_env), '-v', pv + ':/var/lib/postgresql/data', pg['Image'])
        ready = False
        for _ in range(60):
            try:
                run('docker', 'exec', pn, 'pg_isready', '-U', 'evolution', '-d', 'evolution_api')
                ready = True
                break
            except Exception:
                time.sleep(1)
        if not ready:
            raise ValueError('PostgreSQL de validacao nao iniciou.')
        restore_postgres(folder, pn)
        # Disable clone-only integration records before starting the isolated API.
        sql = """DO $$DECLARE r RECORD; BEGIN FOR r IN SELECT table_schema,table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND column_name='enabled' AND table_name IN ('Webhook','Chatwoot','Typebot','Dify','Openai','Evoai','N8n','Rabbitmq','Sqs') LOOP EXECUTE format('UPDATE %I.%I SET %I=FALSE',r.table_schema,r.table_name,r.column_name); END LOOP; END$$;"""
        run('docker', 'exec', pn, 'psql', '-U', 'evolution', '-d', 'evolution_api', '-v', 'ON_ERROR_STOP=1', '-c', sql)
        created.append(rn)
        run('docker', 'create', '--name', rn, '--network', network, '--label', 'vpscloud.upgrade.check=' + token,
            '-v', rv + ':/data', redis['Image'], 'redis-server', '--appendonly', 'no')
        run('docker', 'cp', str(folder / 'redis.rdb'), rn + ':/data/dump.rdb')
        run('docker', 'start', rn)
        values = environment(info)
        uri = urllib.parse.urlsplit(values['DATABASE_CONNECTION_URI'])
        values['DATABASE_CONNECTION_URI'] = urllib.parse.urlunsplit((uri.scheme, 'evolution:' + password + '@' + pn + ':5432', uri.path, uri.query, ''))
        values['DATABASE_PASSWORD'] = password
        values['CACHE_REDIS_URI'] = 'redis://' + rn + ':6379/6'
        values['NODE_OPTIONS'] = values.get('NODE_OPTIONS', '').replace('--require=/evolution/ops-monitor/monitor-hook.cjs', '').strip()
        values['SERVER_URL'] = 'http://127.0.0.1:8080'
        for feature in ['WEBHOOK_GLOBAL', 'RABBITMQ', 'SQS', 'KAFKA', 'NATS', 'CHATWOOT', 'TYPEBOT', 'DIFY', 'OPENAI', 'N8N', 'EVOAI']:
            values[feature + '_ENABLED'] = 'false'
        api_env = folder / 'rehearsal-api.env'
        write_env(api_env, values)
        created.append(an)
        run('docker', 'run', '-d', '--name', an, '--network', network, '--label', 'vpscloud.upgrade.check=' + token,
            '--log-driver', 'json-file', '--log-opt', 'max-size=5m', '--log-opt', 'max-file=2', '--env-file', str(api_env), target['Id'])
        before = json.loads((folder / 'before-upgrade.json').read_text())
        wait(an, '2.3.7', before['instances'])
        if database_instances(pn) != before['database_instances']:
            raise ValueError('Instancias do banco divergiram na copia isolada.')
        print('Migracoes e instancias validadas em copia isolada sem acesso ao WhatsApp.')
    except Exception:
        for name in created:
            try:
                log = subprocess.check_output(['docker', 'logs', '--tail', '200', name], stderr=subprocess.STDOUT)
                (folder / (name + '.private.log')).write_bytes(log)
            except Exception:
                pass
        raise
    finally:
        for name in reversed(created):
            try:
                if inspect(name)['Config'].get('Labels', {}).get('vpscloud.upgrade.check') == token:
                    run('docker', 'rm', '-f', name)
            except Exception:
                pass
        for name in reversed(volumes):
            try:
                if json.loads(run('docker', 'volume', 'inspect', name))[0].get('Labels', {}).get('vpscloud.upgrade.check') == token:
                    run('docker', 'volume', 'rm', name)
            except Exception:
                pass
        if net:
            try:
                details = json.loads(run('docker', 'network', 'inspect', network))[0]
                if details.get('Labels', {}).get('vpscloud.upgrade.check') == token:
                    run('docker', 'network', 'rm', network)
            except Exception:
                pass


def restore_redis(folder, redis, password):
    data = Path(volume(redis, '/data')['Source'])
    stat = (data / 'dump.rdb').stat() if (data / 'dump.rdb').exists() else data.stat()
    run('docker', 'stop', REDIS)
    previous = folder / 'redis-before-rollback'
    previous.mkdir()
    for item in list(data.iterdir()):
        shutil.move(str(item), str(previous / item.name))
    shutil.copyfile(str(folder / 'redis.rdb'), str(data / 'dump.rdb'))
    os.chown(str(data / 'dump.rdb'), stat.st_uid, stat.st_gid)
    os.chmod(str(data / 'dump.rdb'), 0o600)
    name = 'evolution_upgrade_restore_' + uuid.uuid4().hex[:12]
    file = folder / 'redis-restore.env'
    write_env(file, {'RESTORE_REDIS_PASSWORD': password})
    made = False
    try:
        run('docker', 'run', '-d', '--name', name, '--network', 'none', '--env-file', str(file),
            '-v', volume(redis, '/data')['Name'] + ':/data', '--entrypoint', '/bin/sh', redis['Image'],
            '-c', 'exec redis-server --appendonly no --requirepass "$RESTORE_REDIS_PASSWORD"')
        made = True
        for _ in range(30):
            try:
                run('docker', 'exec', '-e', 'REDISCLI_AUTH=' + password, name, 'redis-cli', 'PING')
                break
            except Exception:
                time.sleep(1)
        run('docker', 'exec', '-e', 'REDISCLI_AUTH=' + password, name, 'redis-cli', 'CONFIG', 'SET', 'appendonly', 'yes')
        for _ in range(60):
            state = run('docker', 'exec', '-e', 'REDISCLI_AUTH=' + password, name, 'redis-cli', 'INFO', 'persistence')
            if 'aof_rewrite_in_progress:0' in state and 'aof_last_bgrewrite_status:ok' in state:
                break
            time.sleep(1)
        else:
            raise ValueError('Nao foi possivel reconstruir AOF para recuperacao.')
        run('docker', 'stop', name)
    finally:
        if made:
            run('docker', 'rm', '-f', name)
    run('docker', 'start', REDIS)


def main():
    if os.geteuid() != 0:
        raise ValueError('Execute como root.')
    os.umask(0o077)
    info, pg, redis = inspect(API), inspect(PG), inspect(REDIS)
    run('docker', 'pull', IMAGE)
    target = json.loads(run('docker', 'image', 'inspect', IMAGE))[0]
    if info['Image'] == target['Id']:
        print('API ja utiliza a imagem 2.3.7 validada.')
        return
    before = probe(API)
    if str(before['version']).lstrip('v') != '2.3.4':
        raise ValueError('Atualizacao automatica validada somente de 2.3.4 para 2.3.7; versao atual preservada.')
    if info['HostConfig']['NetworkMode'] != 'evolution_v2_net':
        raise ValueError('Rede nao padrao; API preservada.')
    volume(pg, '/var/lib/postgresql/data')
    volume(redis, '/data')
    validate_backends(info, pg, redis)
    validate_exclusive_volumes(pg, redis)
    if not all(x['State']['Running'] for x in [info, pg, redis]):
        raise ValueError('Servicos devem estar ativos antes do backup.')
    before['database_instances'] = database_instances(PG)
    check_capacity(pg, redis)
    spec = importlib.util.spec_from_file_location('vpscloud_monitor_upgrade', PROJECT / 'monitor/evolution-enable-monitor.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    changed = json.loads(json.dumps(info))
    changed['Image'] = target['Id']
    for key in ['Entrypoint', 'Cmd', 'WorkingDir', 'User']:
        changed['Config'][key] = target['Config'].get(key)
    helper.recreate_args(changed, PROJECT / 'unused-validation.env', with_monitor=False)
    subprocess.check_call([BACKUP_HELPER], env=dict(os.environ, EVOLUTION_BACKUP_KEEP_API_STOPPED='1'))
    folder, renamed, production = None, False, False
    old = API + '_before_upgrade_' + time.strftime('%Y%m%d_%H%M%S')
    try:
        folder = Path((PROJECT / 'backups/LATEST-SESSION-BACKUP').read_text().strip())
        if folder.resolve().parent != (PROJECT / 'backups').resolve():
            raise ValueError('Pasta de backup inesperada.')
        check_backup(folder)
        (folder / 'before-upgrade.json').write_text(json.dumps(before))
        rehearsal(folder, info, pg, redis, target)
        config = folder / 'production-upgrade.env'
        write_env(config, environment(info))
        args = helper.recreate_args(changed, config, with_monitor=False)
        run('docker', 'update', '--restart=no', API)
        run('docker', 'rename', API, old)
        renamed, production = True, True
        run(*args)
        wait(API, '2.3.7', before['instances'])
        if database_instances(PG) != before['database_instances']:
            raise ValueError('Instancias divergiram depois da atualizacao.')
        (folder / 'UPGRADE-COMPLETE').write_text('2.3.7 validated\n')
        print('API atualizada e validada em 2.3.7. Backup: ' + str(folder))
    except Exception:
        if production:
            try:
                try:
                    run('docker', 'update', '--restart=no', API)
                    run('docker', 'stop', '-t', '30', API)
                    run('docker', 'rename', API, API + '_upgrade_failed_' + str(os.getpid()))
                except Exception:
                    pass
                restore_postgres(folder, PG)
                password = urllib.parse.unquote(urllib.parse.urlsplit(environment(info)['CACHE_REDIS_URI']).password or '')
                restore_redis(folder, redis, password)
            except Exception:
                raise ValueError('Recuperacao automatica incompleta. API permanece parada; restaure o backup privado: ' + str(folder))
        if renamed:
            run('docker', 'rename', old, API)
        run('docker', 'update', '--restart=always', API)
        run('docker', 'start', API)
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error) if isinstance(error, ValueError) else 'Atualizacao abortada. Confira o backup privado e o estado da API antes de repetir.', file=sys.stderr)
        sys.exit(1)

