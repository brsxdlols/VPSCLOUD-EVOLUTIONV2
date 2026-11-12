#!/usr/bin/env python3
"""Explicit installer policy: back up once, log out existing Baileys pairings, retain instances."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse

PROJECT = Path('/opt/vpscloud-evolution-v2')
API = 'evolution_v2_api'
BACKUP_HELPER = '/usr/local/sbin/evolution-backup'
OWNERS = {}
REQUEST = """(async()=>{const r=await fetch('http://127.0.0.1:8080'+process.env.RESET_PATH,{method:process.env.RESET_METHOD,headers:{apikey:process.env.AUTHENTICATION_API_KEY},signal:AbortSignal.timeout(20000)});const text=await r.text();let body;try{body=JSON.parse(text)}catch{body={}};console.log(JSON.stringify({http:r.status,body}))})().catch(()=>process.exit(1))"""


def api(method, path):
    out = subprocess.check_output(['docker', 'exec', '-e', 'RESET_METHOD=' + method, '-e', 'RESET_PATH=' + path,
                                   API, 'node', '-e', REQUEST], stderr=subprocess.DEVNULL, universal_newlines=True)
    return json.loads(out)


def instances():
    response = api('GET', '/instance/fetchInstances')
    if response['http'] != 200 or not isinstance(response['body'], list):
        raise ValueError('Nao foi possivel inventariar instancias; logout nao executado.')
    result = []
    OWNERS.clear()
    for row in response['body']:
        item = row.get('instance') or row
        if row.get('integration', item.get('integration')) not in (None, '', 'WHATSAPP-BAILEYS'):
            raise ValueError('Integracao sem pareamento QR exige revisao manual; logout nao executado.')
        name = row.get('name') or item.get('instanceName') or row.get('instanceName')
        if not isinstance(name, str) or not name:
            raise ValueError('Inventario de instancias invalido; logout nao executado.')
        result.append(name)
        OWNERS[name] = row.get('ownerJid') or item.get('ownerJid') or item.get('owner')
    return sorted(set(result))


def state(name):
    response = api('GET', '/instance/connectionState/' + urllib.parse.quote(name, safe=''))
    if response['http'] != 200:
        return None
    return response['body'].get('instance', {}).get('state')


def main():
    if os.geteuid() != 0:
        raise ValueError('Execute como root.')
    os.umask(0o077)
    names = instances()
    if not names:
        print('Nenhuma instancia existente para desconectar.')
        return
    # A failed backup must never reach the first DELETE.
    subprocess.check_call([BACKUP_HELPER])
    folder = Path((PROJECT / 'backups/LATEST-SESSION-BACKUP').read_text().strip())
    if folder.resolve().parent != (PROJECT / 'backups').resolve():
        raise ValueError('Backup fora da pasta esperada; logout nao executado.')
    subprocess.check_call(['sha256sum', '-c', 'SHA256SUMS'], cwd=str(folder), stdout=subprocess.DEVNULL)
    ready = False
    for _ in range(60):
        try:
            if api('GET', '/instance/fetchInstances')['http'] == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(2)
    if not ready:
        raise ValueError('API nao retornou depois do backup; logout nao executado.')
    if instances() != names:
        raise ValueError('Lista de instancias mudou; confirme o inventario antes de repetir.')
    results = []
    for name in names:
        label = re.sub(r'[\r\n]', ' ', name)[:100]
        current = state(name)
        if current == 'close' and not OWNERS.get(name):
            results.append({'instance': name, 'status': 'already_disconnected'})
            print('Instancia ja desconectada: ' + label)
            continue
        response = api('DELETE', '/instance/logout/' + urllib.parse.quote(name, safe=''))
        if response['http'] not in (200, 201):
            (folder / 'pairing-reset.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
            raise ValueError('Logout nao confirmado em ' + label + '; verifique o estado antes de repetir.')
        closed = False
        for _ in range(20):
            if state(name) == 'close':
                closed = True
                break
            time.sleep(1)
        if not closed:
            raise ValueError('Instancia nao confirmou estado desconectado: ' + label)
        results.append({'instance': name, 'status': 'logout_confirmed'})
        (folder / 'pairing-reset.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print('Logout confirmado: ' + label + '. Conecte novamente pelo QR Code.')
    print('Pareamentos existentes encerrados. Instancias e historico preservados; backup nao reativa credenciais revogadas.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error) if isinstance(error, ValueError) else 'Falha na reconexao obrigatoria; confira as instancias e o backup antes de repetir.', file=sys.stderr)
        sys.exit(1)

