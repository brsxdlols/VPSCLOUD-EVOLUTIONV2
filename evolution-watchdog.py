#!/usr/bin/env python3
"""Monitor the standard deployment; never recreate containers or WhatsApp sessions."""
import fcntl
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import syslog
import time
import urllib.parse
import urllib.request
import uuid

CONFIG = Path('/opt/vpscloud-evolution-v2/monitor/config.json')
STATE_DIR = Path('/opt/vpscloud-evolution-v2/monitor')
MAINTENANCE = Path('/run/vpscloud-evolution-maintenance')
BUSY_LOCKS = [Path('/run/lock/vpscloud-evolution-session.lock'),
              Path('/run/lock/vpscloud-evolution-install.lock')]
CONTAINERS = ['evolution_v2_postgres', 'evolution_v2_redis', 'evolution_v2_api']


def log_event(level, text):
    line = time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + str(text).replace('\n', ' ').replace('\r', ' ')[:2000] + '\n'
    try:
        fd = os.open('/var/log/vpscloud-evolution-watchdog.log', os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'a') as stream:
            stream.write(line)
    except OSError:
        syslog.syslog(level, 'Evolution: falha ao escrever log do monitor')


def disk_status():
    usage = shutil.disk_usage('/')
    pct = int(100 * usage.used / usage.total) if usage.total else 100
    info = {'used_percent': pct, 'free_gib': round(usage.free / (1024 ** 3), 1)}
    issue = 'DISCO_CRITICO' if pct >= 90 or usage.free < 1024 ** 3 else 'DISCO_ATENCAO' if pct >= 80 else None
    return info, ([issue] if issue else [])


def run(args, timeout=10):
    try:
        r = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=timeout, universal_newlines=True)
        return r.returncode, r.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return 124, ''


def atomic_json(path, value):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as out:
        os.chmod(str(tmp), 0o600)
        json.dump(value, out, ensure_ascii=False)
        out.flush()
        os.fsync(out.fileno())
    os.replace(str(tmp), str(path))


def telegram_request(token, method, data, content_type):
    try:
        req = urllib.request.Request(
            'https://api.telegram.org/bot' + token + '/' + method,
            data=data, headers={'Content-Type': content_type}, method='POST')
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response).get('ok') is True
    except Exception:
        # URLs/exceptions can contain the token. Never write them to logs.
        return False


def notify(config, text):
    token = config.get('telegram_bot_token', '')
    chat = config.get('telegram_chat_id', '')
    if not token or not chat:
        log_event(syslog.LOG_WARNING, 'Evolution: Telegram ainda nao configurado')
        return False
    kind = config.get('_alert_image', '')
    if kind in ('critical', 'whatsapp', 'recovery'):
        image = STATE_DIR / 'assets' / (kind + '.png')
        if image.is_file():
            try:
                boundary = 'EvolutionAlert' + uuid.uuid4().hex
                caption = text if len(text) <= 1024 else text[:900] + '\n(Detalhes completos nas mensagens seguintes.)'
                parts = []
                for name, value in [('chat_id', str(chat)), ('caption', caption)]:
                    parts.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="' + name + '"\r\n\r\n' + value + '\r\n').encode())
                parts.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="photo"; filename="' + kind + '.png"\r\nContent-Type: image/png\r\n\r\n').encode())
                parts.extend([image.read_bytes(), ('\r\n--' + boundary + '--\r\n').encode()])
                if telegram_request(token, 'sendPhoto', b''.join(parts), 'multipart/form-data; boundary=' + boundary):
                    if len(text) <= 1024:
                        return True
                else:
                    log_event(syslog.LOG_WARNING, 'Evolution: imagem nao entregue; tentando alerta em texto')
            except OSError:
                log_event(syslog.LOG_WARNING, 'Evolution: imagem indisponivel; tentando alerta em texto')
    for start in range(0, len(text), 3900):
        data = urllib.parse.urlencode({'chat_id': chat, 'text': text[start:start + 3900]}).encode()
        if not telegram_request(token, 'sendMessage', data, 'application/x-www-form-urlencoded'):
            log_event(syslog.LOG_ERR, 'Evolution: falha ao entregar alerta Telegram')
            return False
    return True


def attempt(state, key, command, now):
    actions = state.setdefault('last_actions', {})
    if now - actions.get(key, 0) < 300:
        return
    actions[key] = now
    code, _ = run(command, timeout=45)
    log_event(syslog.LOG_WARNING, 'Evolution: tentativa de recuperacao %s rc=%s' % (key, code))


def inspect_health(config, state, now):
    issues = []
    if run(['docker', 'info'], timeout=8)[0] != 0:
        # A live but unresponsive dockerd is not restarted automatically: that
        # could interrupt unrelated MK-AUTH services. Alert for operator action.
        if run(['pgrep', '-x', 'dockerd'])[0] == 1:
            if Path('/run/systemd/system').is_dir():
                command = ['systemctl', 'start', 'docker']
            elif Path('/etc/init.d/docker').exists():
                command = ['/etc/init.d/docker', 'start']
            else:
                command = None
            if command:
                attempt(state, 'docker_start', command, now)
        return ['DOCKER_INDISPONIVEL']
    for container in CONTAINERS:
        code, running = run(['docker', 'inspect', '--format', '{{.State.Running}}', container])
        if code:
            issues.append('CONTAINER_AUSENTE:' + container)
        elif running != 'true':
            issues.append('CONTAINER_PARADO:' + container)
            attempt(state, container + '_start', ['docker', 'start', container], now)
    if issues:
        return issues
    instances = [x['name'] for x in config.get('instances', []) if x.get('enabled')]
    # API credentials stay inside the existing container; only state is returned.
    probe = """(async()=>{try{const h={apikey:process.env.AUTHENTICATION_API_KEY};const root=await fetch('http://127.0.0.1:8080/',{signal:AbortSignal.timeout(4000)});const out={api:root.status,instances:[]};let metadata=[];try{const mr=await fetch('http://127.0.0.1:8080/instance/fetchInstances',{headers:h,signal:AbortSignal.timeout(4000)});if(mr.ok)metadata=await mr.json()}catch{}for(const name of JSON.parse(process.env.HEALTH_INSTANCES)){const r=await fetch('http://127.0.0.1:8080/instance/connectionState/'+encodeURIComponent(name),{headers:h,signal:AbortSignal.timeout(4000)});const o=await r.json();const entry=Array.isArray(metadata)?metadata.find(x=>(x.name||x.instance?.instanceName)===name):null;const jid=entry?.ownerJid||'';const phone=/^[0-9]{8,15}(?::[0-9]+)?@s\.whatsapp\.net$/.test(jid)?'+'+jid.split('@')[0].split(':')[0]:null;out.instances.push({name,http:r.status,state:o.instance?.state||'unknown',phone})}console.log(JSON.stringify(out))}catch{process.exit(1)}})()"""
    code, output = run(['docker', 'exec', '-e', 'HEALTH_INSTANCES=' + json.dumps(instances),
                        'evolution_v2_api', 'node', '-e', probe], timeout=max(15, 5 * len(instances) + 10))
    if code:
        return ['API_SEM_RESPOSTA']
    try:
        result = json.loads(output)
    except ValueError:
        return ['API_RESPOSTA_INVALIDA']
    if result.get('api') != 200:
        return ['API_HTTP_' + str(result.get('api'))]
    numbers = state.setdefault('last_numbers', {})
    for row in result.get('instances', []):
        if row.get('phone'):
            numbers[row['name']] = {'number': row['phone'], 'last_identified': now}
        if row.get('http') != 200:
            issues.append('INSTANCIA_SEM_RESPOSTA:' + row['name'])
        elif row.get('state') != 'open':
            issues.append('WHATSAPP_DESCONECTADO:' + row['name'])
    return issues


def update_one(config, state, issues, now, boot_grace=False):
    state['last_check'] = now
    state['issues'] = sorted(issues)
    state['healthy'] = not bool(issues)
    label = str(config.get('label', 'MK-AUTH / Evolution'))
    if config.get('_disk_line'):
        label += '\n' + config['_disk_line']
    if config.get('_phone_line'):
        label += '\n' + config['_phone_line']
    if issues:
        state['failures'] = state.get('failures', 0) + 1
        key = ', '.join(sorted(issues))
        log_event(syslog.LOG_WARNING, 'Evolution: ' + key)
        due = (key != state.get('alert_key') or now - state.get('last_alert', 0) >= 1800)
        if state['failures'] >= 2 and due and not boot_grace:
            target = dict(config)
            target['_alert_image'] = '' if all(x.startswith('DISCO_') for x in issues) else 'whatsapp' if all(x.startswith(('WHATSAPP_', 'INSTANCIA_')) for x in issues) else 'critical'
            if notify(target, label + '\nALERTA: ' + key + '\nCobrancas podem nao estar sendo enviadas. Verifique a instancia.'):
                state['alert_key'] = key
                state['last_alert'] = now
    else:
        state['failures'] = 0
        if state.get('alert_key'):
            target = dict(config)
            disk_only = all(x.startswith('DISCO_') for x in state['alert_key'].split(', '))
            target['_alert_image'] = '' if disk_only else 'recovery'
            recovered = 'Espaco em disco voltou ao limite seguro.' if disk_only else 'WhatsApp da instancia conectado.' if config.get('_scope') == 'instance' else 'Docker e API respondem normalmente.'
            if notify(target, label + '\nRECUPERADO: ' + recovered + ' Isso nao valida entrega de cobrancas anteriores.'):
                state['alert_key'] = ''
                state['last_alert'] = now


def update_alerts(config, state, issues, now, boot_grace=False):
    state.update(last_check=now, issues=sorted(issues), healthy=not bool(issues))
    conditions = state.setdefault('conditions', {})
    global_issues = [x for x in issues if not x.startswith(('WHATSAPP_', 'INSTANCIA_'))]
    general = dict(config)
    disk = state.get('disk', {})
    if disk and any(x.startswith('DISCO_') for x in issues):
        general['_disk_line'] = 'Disco: %s%% ocupado; %s GiB livres' % (disk['used_percent'], disk['free_gib'])
    known = state.get('last_numbers', {})
    lines = [x['name'] + ': ' + known[x['name']]['number'] for x in config.get('instances', []) if x.get('enabled') and x['name'] in known]
    if lines:
        general['_phone_line'] = 'Ultimos numeros identificados:\n' + '\n'.join(lines)
    update_one(general, conditions.setdefault('docker_api', {}), global_issues, now, boot_grace)
    if global_issues:
        return
    for item in config.get('instances', []):
        if not item.get('enabled'):
            continue
        name = item['name']
        target = dict(config)
        target['_scope'] = 'instance'
        target['label'] = config.get('label', 'Evolution') + ' / ' + name
        number = state.get('last_numbers', {}).get(name, {}).get('number')
        disconnected = any(x.endswith(':' + name) for x in issues)
        target['_phone_line'] = (('Ultimo numero identificado: ' if disconnected else 'WhatsApp: ') + number) if number else 'WhatsApp: numero ainda nao identificado'
        target['telegram_bot_token'] = item.get('telegram_bot_token') or config.get('telegram_bot_token', '')
        target['telegram_chat_id'] = item.get('telegram_chat_id') or config.get('telegram_chat_id', '')
        per_instance = [x for x in issues if x.endswith(':' + name) and x.startswith(('WHATSAPP_', 'INSTANCIA_'))]
        update_one(target, conditions.setdefault('instance:' + name, {}), per_instance, now, boot_grace)


def main():
    if '--status' in sys.argv:
        path = STATE_DIR / 'state.json'
        print(path.read_text() if path.exists() else 'Ainda sem verificacao.')
        return 0
    if os.geteuid() != 0:
        print('Execute como root.', file=sys.stderr)
        return 1
    os.umask(0o077)
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE_DIR / 'lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        if MAINTENANCE.exists() or any(path.exists() for path in BUSY_LOCKS):
            return 0
        if CONFIG.exists() and (CONFIG.stat().st_mode & 0o077):
            log_event(syslog.LOG_ERR, 'Evolution: arquivo de configuracao deve ter modo 600')
            return 1
        config = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
        path = STATE_DIR / 'state.json'
        try:
            state = json.loads(path.read_text())
        except (FileNotFoundError, ValueError):
            state = {}
        now = int(time.time())
        issues = inspect_health(config, state, now)
        state['disk'], disk_issues = disk_status()
        issues.extend(disk_issues)
        try:
            boot_grace = float(Path('/proc/uptime').read_text().split()[0]) < 180
        except (OSError, ValueError):
            boot_grace = False
        update_alerts(config, state, issues, now, boot_grace)
        atomic_json(path, state)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        log_event(syslog.LOG_ERR, 'Evolution: watchdog falhou; verificar configuracao e execucao')
        sys.exit(1)
