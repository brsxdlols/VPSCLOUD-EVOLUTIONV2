#!/usr/bin/env python3
"""Install boot/watchdog integration for the standard layout; retain old API."""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse

PROJECT = Path('/opt/vpscloud-evolution-v2')
API = 'evolution_v2_api'
MONITOR = PROJECT / 'monitor'
RECEIPT = Path('/opt/mk-auth/dados/Recibo_Evolution/settings.json')
WEB_BRIDGE = Path('/opt/mk-auth/dados/evolution/bridge.json')
MAINTENANCE = Path('/run/vpscloud-evolution-maintenance')


def command(args):
    return subprocess.check_output(args, stderr=subprocess.DEVNULL, universal_newlines=True).strip()


def recreate_args(info, env_file, with_monitor=True):
    host = info['HostConfig']
    if host.get('NetworkMode') != 'evolution_v2_net':
        raise ValueError('Rede nao padrao: adaptacao manual necessaria')
    if host.get('Privileged') or host.get('Devices') or host.get('SecurityOpt') or host.get('CapAdd') or host.get('CapDrop') or host.get('Links') or host.get('Dns') or host.get('ExtraHosts'):
        raise ValueError('Configuracao Docker adicional: adaptacao manual necessaria')
    if host.get('Memory') or host.get('NanoCpus') or host.get('CpuQuota') or host.get('CpuShares') or host.get('PidMode') or host.get('ReadonlyRootfs'):
        raise ValueError('Restricoes Docker adicionais: adaptacao manual necessaria')
    conf = info['Config']
    entrypoint = conf.get('Entrypoint') or []
    cmd = conf.get('Cmd') or []
    if not isinstance(entrypoint,list) or not isinstance(cmd,list) or not all(isinstance(x,str) for x in entrypoint+cmd) or not entrypoint+cmd:
        raise ValueError('Comando de inicializacao invalido; container atual preservado')
    if conf.get('User') not in ('', 'root', '0', None):
        raise ValueError('Usuario Docker nao padrao')
    args = ['docker', 'run', '-d', '--name', API, '--restart', 'always', '--network', host['NetworkMode'], '--env-file', str(env_file)]
    log = host.get('LogConfig') or {}
    if log.get('Type'):
        args += ['--log-driver', log['Type']]
    for key, value in (log.get('Config') or {}).items():
        args += ['--log-opt', key + '=' + value]
    for port, binds in (host.get('PortBindings') or {}).items():
        for binding in binds or []:
            ip = binding.get('HostIp') or '0.0.0.0'
            if ':' in ip:
                ip = '[' + ip + ']'
            args += ['-p', ip + ':' + binding['HostPort'] + ':' + port]
    for mount in info.get('Mounts', []):
        if with_monitor and mount['Destination'] == '/evolution/ops-monitor':
            continue
        if mount['Type'] == 'bind':
            source = mount['Source']
        elif mount['Type'] == 'volume' and mount.get('Name'):
            source = mount['Name']
        else:
            raise ValueError('Mount nao suportado')
        args += ['-v', source + ':' + mount['Destination'] + (':ro' if not mount['RW'] else ':rw')]
    if with_monitor: args += ['-v', str(MONITOR) + ':/evolution/ops-monitor:rw']
    for key, value in (conf.get('Labels') or {}).items():
        args += ['--label', key + '=' + value]
    # Explicitly reproduce the existing executable and arguments, independent of image defaults.
    args += ['--entrypoint',entrypoint[0] if entrypoint else '']
    if conf.get('WorkingDir'): args += ['--workdir',conf['WorkingDir']]
    args.append(info['Image'])
    args += entrypoint[1:]+cmd
    return args


def key_env(env, requested):
    old = next((x.split('=',1)[1] for x in env if x.startswith('AUTHENTICATION_API_KEY=')), '')
    new = requested or old
    if requested and not re.fullmatch(r'[A-Za-z0-9._-]{6,128}',requested):
        raise ValueError('API Key Global invalida; use de 6 a 128 letras, numeros, ponto, hifen ou sublinhado.')
    result = [x for x in env if not x.startswith('AUTHENTICATION_API_KEY=')]
    result.append('AUTHENTICATION_API_KEY='+new)
    return result, old, new


def key_updates(old, new):
    updates = {}
    path = PROJECT / 'evolution-v2.env'
    if not path.is_file(): raise ValueError('ENV principal ausente; chave preservada.')
    text = path.read_text()
    lines = [x for x in text.splitlines() if not x.startswith('AUTHENTICATION_API_KEY=')]
    updates[path] = '\n'.join(lines+['AUTHENTICATION_API_KEY='+new])+'\n'
    receipt = RECEIPT
    if receipt.is_file():
        saved = json.loads(receipt.read_text())
        current_url = next((x.split('=',1)[1] for x in text.splitlines() if x.startswith('SERVER_URL=')), 'http://127.0.0.1:7070')
        origin = urllib.parse.urlsplit(current_url); target = urllib.parse.urlsplit(saved.get('api_url',''))
        local = target.hostname in ('127.0.0.1','localhost',origin.hostname) and (target.port or 80)==(origin.port or 80)
        if saved.get('token') == old and local:
            saved['token'] = new; updates[receipt] = json.dumps(saved,ensure_ascii=False,indent=2)
    bridge = WEB_BRIDGE
    if bridge.is_file():
        saved = json.loads(bridge.read_text())
        if saved.get('api_key') == old:
            saved['api_key'] = new; updates[bridge] = json.dumps(saved)
    return updates


def write_preserving(path, content):
    stat = path.stat(); temp = path.with_name(path.name+'.key-tmp')
    temp.write_text(content); os.chown(str(temp),stat.st_uid,stat.st_gid);os.chmod(str(temp),stat.st_mode & 0o777)
    os.replace(str(temp),str(path))


def configure_docker_boot():
    # Enable the init system actually used on the host; never restart Docker here.
    if Path('/run/systemd/system').is_dir():
        command(['systemctl', 'enable', 'docker'])
    elif Path('/etc/init.d/docker').is_file():
        command(['update-rc.d', 'docker', 'defaults'])
    else:
        raise ValueError('Sistema de inicializacao nao suportado')
    command(['docker', 'update', '--restart=always'] + ['evolution_v2_postgres', 'evolution_v2_redis', API])


def main():
    if os.geteuid() != 0:
        raise ValueError('Execute como root')
    os.umask(0o077)
    key_only = '--key-only' in sys.argv
    for name in ([] if key_only else ['monitor-hook.cjs', 'monitor.html', 'evolution-watchdog.py']):
        if not (MONITOR / name).is_file():
            raise ValueError('Arquivo do monitor ausente: ' + name)
    info = json.loads(command(['docker', 'inspect', API]))[0]
    if not info['State']['Running']:
        raise ValueError('API precisa estar ativa antes da instalacao do painel')
    selected_env, old_key, new_key = key_env(list(info['Config']['Env']),os.environ.get('EVOLUTION_API_KEY',''))
    key_changed = old_key != new_key
    if key_only and not key_changed:
        print('API Key Global mantida.');return 0
    updates = key_updates(old_key,new_key) if key_changed else {}
    originals = {p:p.read_text() for p in updates}
    stamp = time.strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid())
    backup = PROJECT / 'backups' / ('monitor-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    (backup / 'api-inspect.json').write_text(json.dumps(info))
    config_file = MONITOR / 'config.json'
    if not key_only and not config_file.exists():
        config_file.write_text(json.dumps({'label': 'MK-AUTH / Evolution', 'instances': [{'name': 'MKAUTH', 'enabled': True}]}))
    if config_file.exists(): os.chmod(str(config_file), 0o600)
    env = selected_env
    existing = next((x.split('=', 1)[1] for x in env if x.startswith('NODE_OPTIONS=')), '')
    if not key_only and '--require=/evolution/ops-monitor/monitor-hook.cjs' not in existing:
        existing = (existing + ' --require=/evolution/ops-monitor/monitor-hook.cjs').strip()
    env = [x for x in env if not x.startswith('NODE_OPTIONS=')]
    env.append('NODE_OPTIONS=' + existing)
    if any('\n' in value or '\r' in value for value in env):
        raise ValueError('ENV multiline exige adaptacao manual')
    env_file = backup / 'effective.env'
    env_file.write_text('\n'.join(env) + '\n')
    args = recreate_args(info, env_file, with_monitor=not key_only)
    for index,(path,content) in enumerate(originals.items()):
        (backup/('key-config-before-'+str(index))).write_text(content)
    configure_docker_boot()
    loaded = '/evolution/ops-monitor' in [x['Destination'] for x in info['Mounts']] and '--require=/evolution/ops-monitor/monitor-hook.cjs' in ' '.join(info['Config']['Env'])
    reload_marker=MONITOR / '.reload-required'
    if (not key_only and (not loaded or reload_marker.exists())) or key_changed:
        marker = MAINTENANCE
        already_paused = marker.exists()
        marker.touch()
        previous = API + '_before_monitor_' + stamp.replace('-', '_')
        renamed = False
        try:
            command(['docker', 'stop', '-t', '30', API])
            command(['docker', 'update', '--restart=no', API])
            command(['docker', 'rename', API, previous])
            renamed = True
            command(args)
            paths = ['/'] if key_only else ['/', '/monitor/']
            probe = "(async()=>{for(const p of "+json.dumps(paths)+"){let r=await fetch('http://127.0.0.1:8080'+p,{signal:AbortSignal.timeout(3000)});if(r.status!==200)process.exit(1)}let a=await fetch('http://127.0.0.1:8080/instance/fetchInstances',{headers:{apikey:process.env.AUTHENTICATION_API_KEY},signal:AbortSignal.timeout(3000)});if(a.status!==200)process.exit(1)})().catch(()=>process.exit(1))"
            ready = False
            for attempt in range(40):
                result = subprocess.run(['docker', 'exec', API, 'node', '-e', probe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                if result.returncode == 0:
                    ready = True
                    break
                time.sleep(3)
            if not ready:
                raise ValueError('API ou painel nao iniciou; retomando container anterior')
            for path,content in updates.items(): write_preserving(path,content)
        except Exception:
            for path,content in originals.items():
                try: write_preserving(path,content)
                except Exception: print('ATENCAO: configuracao exige restauracao do backup privado.',file=sys.stderr)
            if renamed:
                if subprocess.run(['docker', 'inspect', API], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                    subprocess.run(['docker', 'stop', '-t', '15', API], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    command(['docker', 'update', '--restart=no', API])
                    command(['docker', 'rename', API, API + '_monitor_failed_' + stamp.replace('-', '_')])
                command(['docker', 'rename', previous, API])
            command(['docker', 'update', '--restart=always', API])
            command(['docker', 'start', API])
            raise
        finally:
            if not already_paused:
                if marker.exists():
                    marker.unlink()
    if key_only:
        print('API Key Global atualizada; bancos e sessoes preservados. Backup: '+str(backup));return 0
    cron = Path('/etc/cron.d/vpscloud-evolution-watchdog')
    if cron.exists():
        shutil.copy2(str(cron), str(backup / 'watchdog.cron'))
    cron.write_text('SHELL=/bin/sh\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n* * * * * root /usr/bin/python3 /opt/vpscloud-evolution-v2/monitor/evolution-watchdog.py\n')
    os.chmod(str(cron), 0o644)
    if Path('/run/systemd/system').is_dir():
        command(['systemctl', 'enable', 'cron'])
        command(['systemctl', 'start', 'cron'])
    elif Path('/etc/init.d/cron').is_file():
        command(['update-rc.d', 'cron', 'defaults'])
        command(['/etc/init.d/cron', 'start'])
    else:
        raise ValueError('Cron nao encontrado; configure um agendador antes de considerar o monitor ativo')
    if reload_marker.exists(): reload_marker.unlink()
    print('Monitor instalado. Painel: /monitor/ . Backup: ' + str(backup))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Never print CalledProcessError arguments or process environments.
        print(str(error) if isinstance(error, ValueError) else 'Falha ao instalar monitor; confira servicos e backup.', file=sys.stderr)
        sys.exit(1)
