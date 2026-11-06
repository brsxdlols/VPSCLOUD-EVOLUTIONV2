#!/usr/bin/env python3
"""Install boot/watchdog integration for the standard layout; retain old API."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT = Path('/opt/vpscloud-evolution-v2')
API = 'evolution_v2_api'
MONITOR = PROJECT / 'monitor'


def command(args):
    return subprocess.check_output(args, stderr=subprocess.DEVNULL, universal_newlines=True).strip()


def recreate_args(info, env_file):
    host = info['HostConfig']
    if host.get('NetworkMode') != 'evolution_v2_net':
        raise ValueError('Rede nao padrao: adaptacao manual necessaria')
    if host.get('Privileged') or host.get('Devices') or host.get('SecurityOpt') or host.get('CapAdd') or host.get('CapDrop') or host.get('Links') or host.get('Dns') or host.get('ExtraHosts'):
        raise ValueError('Configuracao Docker adicional: adaptacao manual necessaria')
    if host.get('Memory') or host.get('NanoCpus') or host.get('CpuQuota') or host.get('CpuShares') or host.get('PidMode') or host.get('ReadonlyRootfs'):
        raise ValueError('Restricoes Docker adicionais: adaptacao manual necessaria')
    conf = info['Config']
    if conf.get('Entrypoint') != ['/bin/bash', '-c', '. ./Docker/scripts/deploy_database.sh && npm run start:prod'] or conf.get('Cmd'):
        raise ValueError('Entrypoint nao padrao: adaptacao manual necessaria')
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
        if mount['Destination'] == '/evolution/ops-monitor':
            continue
        if mount['Type'] == 'bind':
            source = mount['Source']
        elif mount['Type'] == 'volume' and mount.get('Name'):
            source = mount['Name']
        else:
            raise ValueError('Mount nao suportado')
        args += ['-v', source + ':' + mount['Destination'] + (':ro' if not mount['RW'] else ':rw')]
    args += ['-v', str(MONITOR) + ':/evolution/ops-monitor:rw']
    for key, value in (conf.get('Labels') or {}).items():
        args += ['--label', key + '=' + value]
    args.append(info['Image'])
    return args


def main():
    if os.geteuid() != 0:
        raise ValueError('Execute como root')
    os.umask(0o077)
    for name in ['monitor-hook.cjs', 'monitor.html', 'evolution-watchdog.py']:
        if not (MONITOR / name).is_file():
            raise ValueError('Arquivo do monitor ausente: ' + name)
    info = json.loads(command(['docker', 'inspect', API]))[0]
    if not info['State']['Running']:
        raise ValueError('API precisa estar ativa antes da instalacao do painel')
    stamp = time.strftime('%Y%m%d-%H%M%S')
    backup = PROJECT / 'backups' / ('monitor-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    (backup / 'api-inspect.json').write_text(json.dumps(info))
    config_file = MONITOR / 'config.json'
    if not config_file.exists():
        config_file.write_text(json.dumps({'label': 'MK-AUTH / Evolution', 'instances': [{'name': 'MKAUTH', 'enabled': True}]}))
    os.chmod(str(config_file), 0o600)
    env = list(info['Config']['Env'])
    existing = next((x.split('=', 1)[1] for x in env if x.startswith('NODE_OPTIONS=')), '')
    if '--require=/evolution/ops-monitor/monitor-hook.cjs' not in existing:
        existing = (existing + ' --require=/evolution/ops-monitor/monitor-hook.cjs').strip()
    env = [x for x in env if not x.startswith('NODE_OPTIONS=')]
    env.append('NODE_OPTIONS=' + existing)
    if any('\n' in value or '\r' in value for value in env):
        raise ValueError('ENV multiline exige adaptacao manual')
    env_file = backup / 'effective.env'
    env_file.write_text('\n'.join(env) + '\n')
    args = recreate_args(info, env_file)
    # Enable the init system actually used on the host; never restart Docker here.
    if Path('/run/systemd/system').is_dir():
        command(['systemctl', 'enable', 'docker'])
    elif Path('/etc/init.d/docker').is_file():
        command(['update-rc.d', 'docker', 'defaults'])
    else:
        raise ValueError('Sistema de inicializacao nao suportado')
    command(['docker', 'update', '--restart=always'] + ['evolution_v2_postgres', 'evolution_v2_redis', API])
    loaded = '/evolution/ops-monitor' in [x['Destination'] for x in info['Mounts']] and '--require=/evolution/ops-monitor/monitor-hook.cjs' in ' '.join(info['Config']['Env'])
    if not loaded:
        marker = Path('/run/vpscloud-evolution-maintenance')
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
            probe = "(async()=>{for(const p of ['/', '/ops/monitor/']){let r=await fetch('http://127.0.0.1:8080'+p,{signal:AbortSignal.timeout(3000)});if(r.status!==200)process.exit(1)}})().catch(()=>process.exit(1))"
            ready = False
            for attempt in range(40):
                result = subprocess.run(['docker', 'exec', API, 'node', '-e', probe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                if result.returncode == 0:
                    ready = True
                    break
                time.sleep(3)
            if not ready:
                raise ValueError('API ou painel nao iniciou; retomando container anterior')
        except Exception:
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
    print('Monitor instalado. Painel: /ops/monitor/ . Backup: ' + str(backup))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Never print CalledProcessError arguments or process environments.
        print(str(error) if isinstance(error, ValueError) else 'Falha ao instalar monitor; confira servicos e backup.', file=sys.stderr)
        sys.exit(1)
