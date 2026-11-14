"""Disposable CI VM only. No customer DB, phone, Telegram token or real login."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def run(*args):return subprocess.check_output(list(args),stderr=subprocess.STDOUT,universal_newlines=True,timeout=240).strip()
def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('VPSCLOUD_CI_WEB_TEST')!='1' or os.geteuid()!=0:raise ValueError('Disposable GitHub Actions runner required.')
    if Path('/opt/mk-auth').exists() or run('docker','ps','-aq'):raise ValueError('Runner not empty; nothing changed.')
    spec=importlib.util.spec_from_file_location('web',ROOT/'evolution-install-web-addon.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
    target=Path('/var/www/html/admin/addons/evolution');target.mkdir(parents=True)
    data=Path('/opt/mk-auth/dados/evolution');data.mkdir(parents=True)
    native=Path('/opt/mk-auth');(native/'include').mkdir();(native/'include/addons.inc.hhvm').write_text("<?php session_name('ci_native_session');session_start();")
    (native/'admin').symlink_to('/var/www/html/admin')
    secret='ab'*32;(data/'bridge.json').write_text(json.dumps({'secret':secret}));os.chmod(str(data/'bridge.json'),0o644)
    shutil.copyfile(str(ROOT/'addon/evolution/index.php'),str(target/'index.php'))
    (target/'addons.class.php').write_text("<?php session_name('ci_native_session');session_start();")
    (target/'login-fixture.php').write_text("<?php session_name('ci_native_session');session_start();$_SESSION['MKA_Logado']=1;header('Location: /admin/addons/evolution/');")
    for name in ['topo.php','menu.php','baixo.php']:(target.parents[1]/name).write_text('')
    script=w.menu('', '172.16.30.25:7070');(target.parent/'addon.js').write_text(script)
    (target.parents[1]/'conf_zap_serv.hhvm').write_text('''<!doctype html><input name="wapp_host"><input name="wapp_login" value="KEEP_INSTANCE"><input name="wapp_pass" type="password" value="KEEP_TOKEN"><select name="wapp_servidor"><option value="">Outro</option><option value="evolution2_api">Evolution2 API</option></select><script>if(location.search.includes('existing=1'))document.querySelector('[name=wapp_host]').value='192.168.99.10:8080';</script><script src="/admin/addons/addon.js"></script>''')
    folder=Path('/opt/vpscloud-evolution-v2/monitor');folder.mkdir(parents=True);os.chmod(str(folder),0o755)
    for name in ['monitor-hook.cjs','monitor.html','mkauth-bridge.cjs']:shutil.copyfile(str(ROOT/name),str(folder/name))
    (folder/'bridge-secret.json').write_text(json.dumps({'secret':secret}))
    run('a2enmod','proxy','proxy_http','proxy_wstunnel','rewrite');conf=Path('/etc/apache2/conf-available/vpscloud-evolution-addon.conf');conf.write_text(w.apache('7070'));run('a2enconf','vpscloud-evolution-addon');run('apache2ctl','-t');run('service','apache2','restart')
    fake="""const e=require('express'),c=require('crypto'),a=e();a.use(e.json());a.get('/',(r,s)=>s.json({version:'2.3.7'}));a.get('/instance/fetchInstances',(r,s)=>{if(r.headers.apikey!=='ci-only-global-key')return s.status(401).end();s.json([{id:'ci-fixture',name:'CI_ONLY_NO_PHONE',integration:'WHATSAPP-BAILEYS',connectionStatus:'close',token:'ci-instance-token',_count:{Message:0,Contact:0,Chat:0}}])});a.use((r,s)=>s.json({}));const server=a.listen(8080,'0.0.0.0');server.on('upgrade',(r,s)=>{if(!r.__vpscloudBridge||!r.url.startsWith('/socket.io/'))return s.destroy();const accept=c.createHash('sha1').update(r.headers['sec-websocket-key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');s.write('HTTP/1.1 101 Switching Protocols\\r\\nUpgrade: websocket\\r\\nConnection: Upgrade\\r\\nSec-WebSocket-Accept: '+accept+'\\r\\n\\r\\n');s.on('data',()=>s.destroy())})"""
    name='evolution_v2_api'
    try:
        run('docker','run','-d','--name',name,'--network','bridge','-p','127.0.0.1:7070:8080','-v',str(folder)+':/bridge','-e','NODE_PATH=/evolution/node_modules','-e','AUTHENTICATION_API_KEY=ci-only-global-key','--entrypoint','node','evoapicloud/evolution-api@sha256:1bd8afc4a6cf48822e6cf02469aeae7bd35a12a6b616eacd1291926307f4d339','-r','/bridge/monitor-hook.cjs','-e',fake)
        time.sleep(3)
        actual_run=w.run
        def fixture_run(*args):
            if args[:3]==('ip','-j','route'):return '[{"prefsrc":"172.16.30.25"}]'
            return actual_run(*args)
        with patch.object(w,'run',side_effect=fixture_run):w.main()
        assert target.stat().st_mode&0o777==0o755
        run('node',str(ROOT/'tests/web_addon_browser.cjs'))
        print('PASS Apache + PHP native-session entry point + pinned Manager browser integration')
    except Exception as error:
        print(str(error))
        if isinstance(error,subprocess.CalledProcessError):print(error.output)
        try:print(run('docker','logs','--tail','80',name))
        except Exception:pass
        raise
    finally:
        try:run('docker','rm','-f',name)
        except Exception:pass
if __name__=='__main__':main()
