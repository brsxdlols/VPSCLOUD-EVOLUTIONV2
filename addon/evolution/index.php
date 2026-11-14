<?php
ob_start();
include __DIR__.'/addons.class.php';
ob_end_clean();
if(session_status()!==PHP_SESSION_ACTIVE || (empty($_SESSION['mka_logado']) && empty($_SESSION['MKA_Logado']))){http_response_code(401);exit('Entre pelo MK-AUTH para acessar a Evolution.');}
$config=json_decode(@file_get_contents('/opt/mk-auth/dados/evolution/bridge.json'),true);
if(!is_array($config)||!preg_match('/^[a-f0-9]{64}$/',$config['secret']??'')){http_response_code(503);exit('Addon ainda nao configurado. Execute o instalador.');}
$expiry=(string)(time()+180);$nonce=bin2hex(random_bytes(16));$token=$expiry.'.'.$nonce;
$token.='.'.hash_hmac('sha256',$token,$config['secret']);
$secure=!empty($_SERVER['HTTPS'])&&$_SERVER['HTTPS']!=='off';
header('Set-Cookie: vpscloud_evolution_bridge='.$token.'; Max-Age=180; Path=/admin/addons/evolution/; HttpOnly; SameSite=Strict'.($secure?'; Secure':''),false);
header('Cache-Control: no-store');header('X-Frame-Options: SAMEORIGIN');
if(isset($_GET['refresh'])){header('Content-Type: application/json');echo '{"ok":true}';exit;}
$view=($_GET['view']??'')==='monitor'?'monitor/':'manager/';
session_write_close();
?><!doctype html><html lang="pt-BR" class="has-navbar-fixed-top"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evolution · MK-AUTH</title><link rel="stylesheet" href="../../estilos/mk-auth.css"><script src="../../scripts/jquery.js"></script><script src="../../scripts/mk-auth.js"></script><style>.evolution-addon{padding:22px 16px}nav.evolution-tabs{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:12px 0}.evolution-tabs a{padding:10px 16px;background:#168664;color:white;border-radius:6px;text-decoration:none}.evolution-addon iframe{width:100%;height:calc(100vh - 230px);min-height:600px;border:0;border-radius:8px;background:#08120f}.evolution-addon p{margin:8px 0;color:#395469}#session-error{color:#a42c28;font-weight:bold}</style></head><body>
<?php include '../../topo.php';include '../../menu.php'; ?>
<main class="evolution-addon"><h1>Evolution API</h1><nav class="evolution-tabs"><a href="?view=manager">Manager</a><a href="?view=monitor">Alertas Telegram</a><a href="../../conf_zap_serv.hhvm?vpscloud_evolution=1">Configurar servidor WhatsApp</a></nav><p>Use a API Key Global para entrar no Manager e no monitor. O acesso usa o mesmo endereco web do MK-AUTH.</p><p id="session-error" role="alert"></p><iframe title="Evolution" src="app/<?php echo $view; ?>" referrerpolicy="same-origin"></iframe></main>
<script>setInterval(async()=>{try{const r=await fetch('index.php?refresh=1',{credentials:'same-origin',cache:'no-store'});const o=await r.json();if(!r.ok||!o.ok)throw Error();}catch{document.getElementById('session-error').textContent='Sessao expirada. Entre novamente pelo MK-AUTH e reabra o addon.';}},90000);</script>
<?php include '../../baixo.php'; ?></body></html>
