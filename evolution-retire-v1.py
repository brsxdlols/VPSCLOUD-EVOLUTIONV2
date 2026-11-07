#!/usr/bin/env python3
"""Retire only the standard, positively identified Evolution V1 deployment."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

NAME = 'evolution_api'
ROOTS = (Path('/opt/evolution'), Path('/opt/evolution-api'), Path('/opt/vpscloud-evolution'))
BACKUPS = Path('/root/evolution-v1-backups')


def docker(*args):
    return subprocess.check_output(['docker'] + list(args), stderr=subprocess.DEVNULL, universal_newlines=True).strip()


def overlap(a, b):
    a, b = Path(a), Path(b)
    return a == b or a in b.parents or b in a.parents


def plan(info, others):
    image = info['Config']['Image']
    tagged_v1 = re.fullmatch(r'(?:atendai|evolutionapi|evoapicloud)/evolution-api:v?1\.\d+(?:\.\d+)?(?:[-.][A-Za-z0-9.-]+)?', image)
    verified_latest = re.fullmatch(r'(?:atendai|evolutionapi|evoapicloud)/evolution-api(?::latest)?', image) and re.fullmatch(r'1\.\d+(?:\.\d+)?(?:[-.][A-Za-z0-9.-]+)?', info.get('_legacy_version',''))
    if not (tagged_v1 or verified_latest):
        raise ValueError('evolution_api nao tem uma imagem V1 reconhecida; nenhum dado removido.')
    roots, volumes = set(), set()
    for mount in info.get('Mounts', []):
        source, destination = mount.get('Source', ''), mount.get('Destination', '')
        if mount['Type'] == 'bind' and not mount.get('RW', True) and source in ('/etc/localtime', '/etc/timezone', '/etc/ssl/certs'):
            continue  # Generic host settings are never removed.
        if not (destination == '/evolution' or destination.startswith('/evolution/')):
            raise ValueError('Mount V1 fora do layout reconhecido; revise antes da remocao.')
        if mount['Type'] == 'volume':
            name = mount.get('Name', '')
            if not re.fullmatch(r'(?:evolution[_-][A-Za-z0-9_.-]+|evo[_-][A-Za-z0-9_.-]+|[a-f0-9]{64})', name) or name.startswith('evolution_v2_'):
                raise ValueError('Volume V1 sem propriedade comprovada; remocao bloqueada.')
            volumes.add(name)
        elif mount['Type'] == 'bind':
            path = Path(source)
            if not path.is_absolute() or path.resolve() != path:
                raise ValueError('Bind V1 com symlink ou caminho inesperado.')
            root = next((r for r in ROOTS if path == r or r in path.parents), None)
            if root is None or root.resolve() != root:
                raise ValueError('Diretorio V1 fora das pastas exclusivas reconhecidas.')
            roots.add(str(root))
        else:
            raise ValueError('Tipo de mount V1 nao suportado.')
        for other in others:
            for shared in other.get('Mounts', []):
                if shared.get('Name') in volumes or (source and shared.get('Source') and overlap(source, shared['Source'])):
                    raise ValueError('Dados da V1 compartilhados com outro container; remocao bloqueada.')
    working = info.get('Config', {}).get('Labels', {}).get('com.docker.compose.project.working_dir') if info.get('Config', {}).get('Labels') else None
    if working and Path(working) in ROOTS:
        if Path(working).resolve() != Path(working): raise ValueError('Pasta Compose V1 com symlink.')
        roots.add(working)
    # Retiring a whole legacy directory must not remove another container's files.
    for root in roots:
        for other in others:
            if any(m.get('Source') and overlap(root, m['Source']) for m in other.get('Mounts', [])):
                raise ValueError('Pasta V1 contem dados de outro container; remocao bloqueada.')
    return {'id': info['Id'], 'image': info['Image'], 'roots': sorted(roots), 'volumes': sorted(volumes), 'networks': sorted(n for n in info.get('NetworkSettings', {}).get('Networks', {}) if n.startswith(('evolution_', 'evolution-')) and not n.startswith('evolution_v2'))}


def inventory():
    ids = docker('ps', '-aq').split()
    all_info = json.loads(docker('inspect', *ids)) if ids else []
    target = next((x for x in all_info if x.get('Name', '').lstrip('/') == NAME), None)
    if target is None:
        return None, []
    if re.fullmatch(r'(?:atendai|evolutionapi|evoapicloud)/evolution-api(?::latest)?',target['Config']['Image']):
        raw = subprocess.check_output(['docker','cp',NAME+':/evolution/package.json','-'],stderr=subprocess.DEVNULL)
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            member = next((x for x in archive if x.isfile() and Path(x.name).name == 'package.json' and x.size < 65536), None)
            if member is not None:
                package = json.loads(archive.extractfile(member).read().decode('utf8'))
                if package.get('name') == 'evolution-api': target['_legacy_version'] = str(package.get('version',''))
    return target, [x for x in all_info if x['Id'] != target['Id']]


def valid_tar(path):
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Backup vazio; V1 preservada.')
    with tarfile.open(str(path)) as archive:
        if not sum(1 for _ in archive):
            raise ValueError('Backup sem catalogo; V1 preservada.')


def retire(info, others):
    owned = plan(info, others)  # All ownership checks precede stop/delete.
    os.umask(0o077)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / ('before-v2-' + time.strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid()))
    backup.mkdir(mode=0o700)
    mounts = [Path(p) for p in owned['roots']] + [Path(m['Source']) for m in info.get('Mounts', []) if m['Type'] == 'volume']
    size = json.loads(docker('image', 'inspect', owned['image']))[0].get('Size', 0)
    writable = json.loads(docker('inspect', '--size', NAME))[0].get('SizeRw', 0)
    estimate = int(size) + int(writable) + 1024 ** 3
    for source in mounts:
        if not source.exists():
            raise ValueError('Dados V1 inacessiveis; backup abortado.')
        estimate += int(subprocess.check_output(['du', '-sk', '--apparent-size', str(source)], universal_newlines=True).split()[0]) * 1024
    if shutil.disk_usage(str(backup)).free < estimate * 2:
        raise ValueError('Espaco insuficiente para backup da V1; nenhuma exclusao executada.')
    (backup / 'inspect.json').write_text(json.dumps(info, indent=2))
    (backup / 'plan.json').write_text(json.dumps(owned, indent=2))
    running = info.get('State', {}).get('Running', False)
    stopped, removed = False, False
    try:
        if running:
            docker('stop', NAME); stopped = True
        docker('image', 'save', '-o', str(backup / 'image.tar'), owned['image'])
        docker('export', '-o', str(backup / 'container.tar'), NAME)
        valid_tar(backup / 'image.tar'); valid_tar(backup / 'container.tar')
        with tarfile.open(str(backup / 'data.tar'), 'w', dereference=False) as archive:
            for index, source in enumerate(mounts):
                archive.add(str(source), arcname='mount-' + str(index))
            if not mounts:
                marker = tarfile.TarInfo('no-external-mounts'); archive.addfile(marker)
        valid_tar(backup / 'data.tar')
        hashes = {}
        for file in ['image.tar', 'container.tar', 'data.tar']:
            digest = hashlib.sha256()
            with (backup / file).open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
            hashes[file] = digest.hexdigest()
        (backup / 'sha256.json').write_text(json.dumps(hashes, indent=2))
        current, remaining = inventory()
        if current is None or plan(current, remaining) != owned:
            raise ValueError('Inventario mudou durante o backup; exclusao cancelada.')
        docker('rm', NAME); removed = True
        for volume in owned['volumes']:
            docker('volume', 'rm', volume)
        for network in owned['networks']:
            details = json.loads(docker('network', 'inspect', network))[0]
            (backup / ('network-' + network + '.json')).write_text(json.dumps(details, indent=2))
            if not details.get('Containers'): docker('network', 'rm', network)
        retired = backup / 'retired-files'; retired.mkdir()
        for index, root in enumerate(owned['roots']):
            shutil.move(root, str(retired / ('root-' + str(index))))
        # A shared image remains available to its other container; never force removal.
        if not any(x.get('Image') == owned['image'] for x in remaining):
            docker('image', 'rm', owned['image'])
        (backup / 'COMPLETE').write_text('V1 retired; new WhatsApp pairing required.\n')
        print('V1 removida: container, volumes exclusivos, pastas identificadas e imagem nao compartilhada.')
        print('Backup privado preservado: ' + str(backup))
    finally:
        if stopped and not removed:
            try: docker('start', NAME)
            except Exception: print('ATENCAO: verifique manualmente o retorno da V1.', file=sys.stderr)


def main():
    if os.geteuid() != 0: raise ValueError('Execute como root.')
    info, others = inventory()
    if info is None: return
    if '--plan' in sys.argv:
        owned = plan(info, others); print('V1 reconhecida; volumes exclusivos: %s; pastas: %s' % (len(owned['volumes']), len(owned['roots']))); return
    retire(info, others)


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(str(error) if isinstance(error, ValueError) else 'Falha ao remover V1. Backup preservado; revise o inventario antes de continuar.', file=sys.stderr)
        sys.exit(1)
