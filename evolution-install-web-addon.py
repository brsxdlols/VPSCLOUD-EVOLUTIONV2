#!/usr/bin/env python3
"""Same-origin MK-AUTH entry point. Apache relays only to the fixed local API."""
from pathlib import Path
import ipaddress
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT=Path('/opt/mk-auth')
PROJECT=Path('/opt/vpscloud-evolution-v2')
PACKAGE=Path(__file__).resolve().parent/'addon/evolution'
CONF=Path('/etc/apache2/conf-available/vpscloud-evolution-addon.conf')

def run(*args):
    return subprocess.check_output(list(args),stderr=subprocess.DEVNULL,universal_newlines=True).strip()

def address(info,route):
    port=next((x['HostPort'] for x in (info['HostConfig'].get('PortBindings') or {}).get('8080/tcp',[]) if x.get('HostIp','0.0.0.0') in ('','0.0.0.0','127.0.0.1')),None)
    if not port or not port.isdigit() or not 1<=int(port)<=65535:raise ValueError('Porta local da API nao reconhecida.')
    source=next((x.get('prefsrc') or x.get('src') for x in route if x.get('prefsrc') or x.get('src')),None)
    ip=ipaddress.ip_address(source or '')
    if ip.version!=4 or ip.is_loopback or ip.is_unspecified or ip.is_multicast:raise ValueError('IP IPv4 do servidor nao identificado.')
    return str(ip)+':'+port,port

def menu(source,host):
    block=(PACKAGE/'native-menu.js').read_text().replace('__EVOLUTION_NATIVE_ADDRESS__',json.dumps(host))
    pattern=r'/\* VPSCLOUD-EVOLUTION-BEGIN \*/.*?/\* VPSCLOUD-EVOLUTION-END \*/\n?'
    return re.sub(pattern,lambda _:block,source,flags=re.S) if '/* VPSCLOUD-EVOLUTION-BEGIN */' in source else source.rstrip()+'\n'+block

def apache(port):
    base='/admin/addons/evolution/app/'
    return '''# Managed by VPSCloud Evolution. Fixed loopback upstream; ticket checked by API hook.
RewriteEngine On
RewriteCond %{HTTP:Upgrade} =websocket [NC]
RewriteRule ^/?admin/addons/evolution/app/(.*)$ ws://127.0.0.1:PORT/admin/addons/evolution/app/$1 [P,L]
<Location "/admin/addons/evolution/app/">
    ProxyPreserveHost On
</Location>
ProxyPass "BASE" "http://127.0.0.1:PORTBASE" connectiontimeout=3 timeout=60
ProxyPassReverse "BASE" "http://127.0.0.1:PORTBASE"
'''.replace('PORT',port).replace('BASE',base)

def main():
    import grp
    if os.geteuid()!=0:raise ValueError('Execute como root.')
    os.umask(0o077)
    target=ROOT/'admin/addons/evolution';data=ROOT/'dados/evolution';monitor=PROJECT/'monitor'
    if not (ROOT/'include/addons.inc.hhvm').is_file() or not (ROOT/'admin/addons/addon.js').is_file():raise ValueError('MK-AUTH nao reconhecido.')
    if not Path('/etc/apache2/apache2.conf').is_file() or not shutil.which('apache2ctl') or not shutil.which('a2enconf'):raise ValueError('Proxy automatico requer Apache2. Configure o proxy equivalente no servidor web utilizado.')
    if not (monitor/'mkauth-bridge.cjs').is_file():raise ValueError('Instale primeiro os auxiliares atualizados do monitor.')
    run('php','-l',str(PACKAGE/'index.php'))
    info=json.loads(run('docker','inspect','evolution_v2_api'))[0]
    host,port=address(info,json.loads(run('ip','-j','route','get','1.1.1.1')))
    try:
        urllib.request.urlopen('http://127.0.0.1:'+port+'/admin/addons/evolution/app/instance/fetchInstances',timeout=5)
        raise ValueError('Protecao do proxy ausente; atualize primeiro o monitor.')
    except urllib.error.HTTPError as e:
        if e.code!=401 or 'Entre novamente pelo addon Evolution' not in e.read().decode('utf8','replace'):raise ValueError('Auxiliar do proxy nao esta carregado. Atualize primeiro o monitor.')
    gid=grp.getgrnam('www-data').gr_gid
    backup=PROJECT/'backups'/('web-addon-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid()))
    backup.mkdir(parents=True,mode=0o700)
    if target.exists():shutil.copytree(str(target),str(backup/'addon-before'),symlinks=True)
    menu_path=ROOT/'admin/addons/addon.js';shutil.copy2(str(menu_path),str(backup/'addon.js'))
    old_conf=CONF.read_bytes() if CONF.exists() else None
    if old_conf is not None:(backup/'apache-before.conf').write_bytes(old_conf)
    data.mkdir(parents=True,exist_ok=True);os.chown(str(data),0,gid);os.chmod(str(data),0o750)
    private=data/'bridge.json'
    saved=json.loads(private.read_text()) if private.exists() else {}
    secret=saved.get('secret') or secrets.token_hex(32)
    if not re.fullmatch('[a-f0-9]{64}',secret):raise ValueError('Segredo do addon invalido; restaure o backup.')
    if private.exists():shutil.copy2(str(private),str(backup/'bridge-before.json'))
    private.write_text(json.dumps({'secret':secret,'address':host}));os.chown(str(private),0,gid);os.chmod(str(private),0o640)
    bridge_secret=monitor/'bridge-secret.json';bridge_secret.write_text(json.dumps({'secret':secret}));os.chmod(str(bridge_secret),0o600)
    target.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(str(PACKAGE/'index.php'),str(target/'index.php'));os.chmod(str(target/'index.php'),0o644)
    link=target/'addons.class.php'
    if not link.exists():link.symlink_to(ROOT/'include/addons.inc.hhvm')
    original=menu_path.read_text();temp=menu_path.with_suffix('.evolution-tmp')
    temp.write_text(menu(original,host));os.chmod(str(temp),menu_path.stat().st_mode&0o777);os.replace(str(temp),str(menu_path))
    try:
        run('a2enmod','proxy','proxy_http','proxy_wstunnel','rewrite')
        CONF.write_text(apache(port));os.chmod(str(CONF),0o644)
        run('a2enconf','vpscloud-evolution-addon')
        run('apache2ctl','-t')
        run('service','apache2','reload')
    except Exception:
        if old_conf is None:
            if CONF.exists():CONF.unlink()
            run('a2disconf','vpscloud-evolution-addon')
        else:CONF.write_bytes(old_conf)
        try:
            run('apache2ctl','-t');run('service','apache2','reload')
        except Exception:pass
        raise ValueError('Proxy nao foi ativado; configuracao Apache anterior preservada. Backup: '+str(backup))
    print('Addon Evolution: /admin/addons/evolution/ ; monitor na aba Alertas Telegram.')
    print('Servidor WhatsApp sugerido: '+host+' (instancia e chave preservadas; grave no MK-AUTH). Backup: '+str(backup))

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(str(e) if isinstance(e,ValueError) else 'Falha ao instalar addon Evolution; consulte o backup privado.',file=sys.stderr);sys.exit(1)
