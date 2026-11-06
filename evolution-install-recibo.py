#!/usr/bin/env python3
"""Install receipt integration without publishing or hardcoding host credentials."""
import grp
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path('/opt/mk-auth')
TARGET = ROOT / 'admin/addons/Recibo_Evolution'
DATA = ROOT / 'dados/Recibo_Evolution'
PACKAGE = Path(__file__).resolve().parent / 'addon'


def command(args):
    return subprocess.check_output(args, stderr=subprocess.DEVNULL, universal_newlines=True).strip()


def literal(source, name):
    match = re.search(r'\$' + re.escape(name) + r'\s*=\s*([\x22\x27])([^\r\n]*?)\1\s*;', source)
    if not match or '\\' in match[2] or '$' in match[2]:
        raise ValueError('Credencial nao literal: use RECIBO_DB_CONFIG com arquivo JSON privado.')
    return match[2]


def native_database(source):
    pattern = r'mysqli_connect\s*\(\s*([\x22\x27])(.*?)\1\s*,\s*([\x22\x27])(.*?)\3\s*,\s*([\x22\x27])(.*?)\5\s*,\s*([\x22\x27])(.*?)\7\s*\)'
    for match in re.finditer(pattern, source, re.S):
        values = [match[x] for x in [2, 4, 6, 8]]
        if values[3] == 'mkradius' and not any('\\' in x or '$' in x or '\n' in x for x in values):
            return dict(zip(['host', 'user', 'password', 'name'], values))
    raise ValueError('Forneca RECIBO_DB_CONFIG (JSON privado com host,user,password,name). Credenciais nao sao presumidas.')


def menu(source):
    marker = '/* VPSCLOUD-RECIBO-BEGIN */'
    block = """/* VPSCLOUD-RECIBO-BEGIN */
;(function(){
 if(typeof add_menu==='undefined'||window.__vpscloudReciboMenu)return;
 window.__vpscloudReciboMenu=true;
 var item=JSON.stringify({plink:window.location.origin+'/admin/addons/Recibo_Evolution/',ptext:'Recibos via WhatsApp',picone:'fa fa-whatsapp'});
 if(typeof add_menu.financeiro==='function')add_menu.financeiro(item);
 if(typeof add_menu.provedor==='function')add_menu.provedor(item);
})();
/* VPSCLOUD-RECIBO-END */
"""
    if marker in source:
        return re.sub(r'/\* VPSCLOUD-RECIBO-BEGIN \*/.*?/\* VPSCLOUD-RECIBO-END \*/\n?', block, source, flags=re.S)
    return source.rstrip() + '\n\n' + block


def main():
    if os.geteuid() != 0:
        raise ValueError('Execute como root')
    os.umask(0o077)
    if not (ROOT / 'include/addons.inc.hhvm').exists() or not (ROOT / 'admin/topo.php').exists():
        raise ValueError('Estrutura MK-AUTH nao reconhecida')
    if not (PACKAGE / 'setup.php').is_file():
        raise ValueError('Pacote de instalacao incompleto')
    if not (Path('/opt/vpscloud-evolution-v2/monitor/evolution-log-policy.sh')).is_file():
        raise ValueError('Instale a politica de logs antes do addon')
    for file in PACKAGE.rglob('*.php'):
        command(['php', '-l', str(file)])
    stamp = time.strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid())
    backup = Path('/opt/vpscloud-evolution-v2/backups') / ('recibo-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    if TARGET.exists():
        shutil.copytree(str(TARGET), str(backup / 'addon-before'), symlinks=True)
    if DATA.exists():
        shutil.copytree(str(DATA), str(backup / 'data-before'), symlinks=True, ignore=shutil.ignore_patterns('log_pagamentos.txt*', 'php-errors.log*', 'last-run'))
    addon_js = ROOT / 'admin/addons/addon.js'
    if not addon_js.is_file():
        raise ValueError('addon.js nao encontrado; nenhuma alteracao aplicada')
    shutil.copy2(str(addon_js), str(backup / 'addon.js'))
    if os.environ.get('RECIBO_DB_CONFIG'):
        db = json.loads(Path(os.environ['RECIBO_DB_CONFIG']).read_text())
    elif (DATA / 'database.php').exists() and (TARGET / 'common.php').exists():
        try:
            command(['php', '-r', "require $argv[1]; $d=recibo_db(); if(!$d->query('SELECT nome FROM vpscloud_recibo_whatsapp LIMIT 0'))exit(1);", str(TARGET / 'common.php')])
            db = None  # Code-only update retains the dedicated account and schema.
        except subprocess.CalledProcessError:
            db = native_database((ROOT / 'admin/config.php').read_text(errors='replace'))
    elif (TARGET / 'index.php').exists():
        source = (TARGET / 'index.php').read_text(errors='replace')
        db = dict(zip(['host', 'user', 'password', 'name'], [literal(source, x) for x in ['host', 'usuario', 'senha', 'db']]))
    else:
        db = native_database((ROOT / 'admin/config.php').read_text(errors='replace'))
    web_group = grp.getgrnam('www-data').gr_gid
    DATA.mkdir(parents=True, exist_ok=True)
    os.chown(str(DATA), 0, web_group)
    os.chmod(str(DATA), 0o2770)
    payload = {'database': db, 'backup': str(backup), 'data': str(DATA)}
    fd, name = tempfile.mkstemp(prefix='recibo-setup-', suffix='.json')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(payload, stream)
        if db is not None:
            command(['php', str(PACKAGE / 'setup.php'), name])
        else:
            command(['php', '-r', "require $argv[1]; $d=recibo_db(); if(!$d->query('SELECT queue_id FROM vpscloud_recibo_delivery LIMIT 0'))exit(1);", str(TARGET / 'common.php')])
    finally:
        os.unlink(name)
    config = DATA / 'settings.json'
    if not config.exists():
        # Generate defaults from our own common library, with no runtime side effects.
        code = "require $argv[1]; echo json_encode(recibo_defaults(),JSON_UNESCAPED_UNICODE);"
        settings = json.loads(command(['php', '-r', code, str(PACKAGE / 'Recibo_Evolution/common.php')]))
        # Standard same-host Evolution config; never print its API key.
        try:
            info = json.loads(command(['docker', 'inspect', 'evolution_v2_api']))[0]
            effective = dict(x.split('=', 1) for x in info['Config']['Env'] if '=' in x)
            settings['token'] = effective.get('AUTHENTICATION_API_KEY', '')
        except Exception:
            pass
        settings['enabled'] = False
        config.write_text(json.dumps(settings, ensure_ascii=False, indent=2))
    os.chown(str(config), 0, web_group)
    os.chmod(str(config), 0o660)
    os.chown(str(DATA / 'database.php'), 0, web_group)
    os.chmod(str(DATA / 'database.php'), 0o640)
    for log in ['log_pagamentos.txt', 'php-errors.log']:
        path = DATA / log
        path.touch(exist_ok=True)
        os.chown(str(path), 0, web_group)
        os.chmod(str(path), 0o660)
    # User confirmed no editor is active. Remove only known editor artifacts from public files.
    for artifact in ['.enviozap.php.swp', 'enviozap.php~', 'index.php~']:
        old = TARGET / artifact
        if old.is_file() and not old.is_symlink():
            shutil.move(str(old), str(backup / artifact))
    # Only replace our addon files; keep its legacy resources in the private backup.
    TARGET.mkdir(parents=True, exist_ok=True)
    for file in (PACKAGE / 'Recibo_Evolution').iterdir():
        if not file.is_file():
            continue
        target = TARGET / file.name
        temp = TARGET / (file.name + '.vpscloud-tmp')
        shutil.copyfile(str(file), str(temp))
        os.chmod(str(temp), 0o644)
        os.replace(str(temp), str(target))
    link = TARGET / 'addons.class.php'
    if not link.exists():
        link.symlink_to(ROOT / 'include/addons.inc.hhvm')
    # Keep DB/schema setup outside the public document root.
    original = addon_js.read_text()
    tmp_menu = addon_js.with_suffix('.vpscloud-tmp')
    tmp_menu.write_text(menu(original))
    os.chmod(str(tmp_menu), addon_js.stat().st_mode & 0o777)
    os.replace(str(tmp_menu), str(addon_js))
    for user in ['root', 'www-data']:
        result = subprocess.run(['crontab', '-u', user, '-l'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
        if result.returncode == 0:
            (backup / ('crontab-' + user)).write_text(result.stdout)
            lines = [x for x in result.stdout.splitlines() if not any('/Recibo_Evolution/' + file in x for file in ['enviozap.php', 'limpar_tabela.php'])]
            if lines != result.stdout.splitlines():
                subprocess.run(['crontab', '-u', user, '-'], input='\n'.join(lines) + '\n', universal_newlines=True, check=True)
    cron = Path('/etc/cron.d/vpscloud-recibo-evolution')
    if cron.exists():
        shutil.copy2(str(cron), str(backup / 'cron-before'))
    cron.write_text('SHELL=/bin/sh\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n* * * * * root /usr/bin/php -d display_errors=0 -d log_errors=1 -d error_log=/opt/mk-auth/dados/Recibo_Evolution/php-errors.log -q /opt/mk-auth/admin/addons/Recibo_Evolution/enviozap.php >> /opt/mk-auth/dados/Recibo_Evolution/php-errors.log 2>&1\n')
    os.chmod(str(cron), 0o644)
    command(['sh', '/opt/vpscloud-evolution-v2/monitor/evolution-log-policy.sh'])
    print('Recibo instalado. Automatico desativado em instalacao nova. Abra /admin/addons/Recibo_Evolution/ . Backup: ' + str(backup))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(str(error) if isinstance(error, ValueError) else 'Falha na instalacao. Backup preservado; nao ative o envio antes da revisao.', file=sys.stderr)
        sys.exit(1)
