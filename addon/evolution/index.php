<?php
$global=isset($_GET['globalkey']);
$picker=isset($_GET['instances'])||$global;
if($picker){
 header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store');header('X-Content-Type-Options: nosniff');
 register_shutdown_function(function(){if(!defined('EVOLUTION_PICKER_READY')){while(ob_get_level())ob_end_clean();http_response_code(401);echo json_encode(['error'=>'Entre novamente pelo MK-AUTH.']);}});
}
ob_start();
include __DIR__.'/addons.class.php';
ob_end_clean();
if($picker)define('EVOLUTION_PICKER_READY',true);
function picker_reply($code,$body){http_response_code($code);echo json_encode($body,JSON_UNESCAPED_UNICODE);exit;}
if($picker && (session_status()!==PHP_SESSION_ACTIVE || (empty($_SESSION['mka_logado']) && empty($_SESSION['MKA_Logado']))))picker_reply(401,['error'=>'Entre novamente pelo MK-AUTH.']);
if(session_status()!==PHP_SESSION_ACTIVE || (empty($_SESSION['mka_logado']) && empty($_SESSION['MKA_Logado']))){http_response_code(401);exit('Entre pelo MK-AUTH para acessar a Evolution.');}
$config=json_decode(@file_get_contents('/opt/mk-auth/dados/evolution/bridge.json'),true);
if($global){
 if(!is_array($config)||empty($config['api_key']))picker_reply(503,['error'=>'Atualize o addon Evolution.']);
 $login=$_SESSION['MKA_Usuario']??'';if(!is_string($login)||$login==='')$login=$_SESSION['MM_Usuario']??'';
 if(!is_string($login)||$login==='')picker_reply(403,['error'=>'Usuario conectado nao identificado. Entre novamente no MK-AUTH.']);
 if(empty($_SESSION['evolution_key_csrf']))$_SESSION['evolution_key_csrf']=bin2hex(random_bytes(32));
 if(($_SERVER['REQUEST_METHOD']??'GET')==='GET')picker_reply(200,['csrf'=>$_SESSION['evolution_key_csrf'],'user'=>$login]);
 if(($_SERVER['REQUEST_METHOD']??'')!=='POST')picker_reply(405,['error'=>'Metodo nao permitido.']);
 if(!is_string($_POST['csrf']??null)||!hash_equals($_SESSION['evolution_key_csrf'],$_POST['csrf']))picker_reply(403,['error'=>'Sessao expirada. Abra a confirmacao novamente.']);
 $password=$_POST['password']??null;
 if(!is_string($password)||$password===''||strlen($password)>1024)picker_reply(400,['error'=>'Informe sua senha do MK-AUTH.']);
 // Reuse MK-AUTH's configured connection; never copy database credentials.
 $connection=function(){ob_start();include_once '/opt/mk-auth/admin/config.php';ob_end_clean();return isset($conn)?$conn:($GLOBALS['conn']??null);};
 $conn=$connection();
 if(!($conn instanceof mysqli))picker_reply(503,['error'=>'Validacao de senha indisponivel nesta versao do MK-AUTH.']);
 require_once __DIR__.'/reauth.php';
 try{
  $valid=evolution_reauth($login,$password,'/opt/mk-auth/dados/evolution/reauth',function($user)use($conn){
   $stmt=$conn->prepare('SELECT sha,ativo FROM sis_acesso WHERE login = ? LIMIT 1');
   if(!$stmt)throw new RuntimeException('Validacao de senha indisponivel.',503);
   $stmt->bind_param('s',$user);if(!$stmt->execute()){ $stmt->close();throw new RuntimeException('Validacao de senha indisponivel.',503); }
   $stmt->bind_result($hash,$active);$found=$stmt->fetch();$stmt->close();return $found?['sha'=>$hash,'ativo'=>$active]:null;
  });
 }catch(RuntimeException $error){unset($password,$_POST['password']);picker_reply($error->getCode()===429?429:503,['error'=>$error->getCode()===429?$error->getMessage():'Nao foi possivel validar a senha no MK-AUTH.']);}
 unset($password,$_POST['password']);
 if(!$valid)picker_reply(403,['error'=>'Senha incorreta ou usuario desativado.']);
 picker_reply(200,['key'=>$config['api_key']]);
}
if($picker){
 if(!is_array($config)||empty($config['api_key'])||empty($config['port'])||!is_int($config['port'])||$config['port']<1||$config['port']>65535)picker_reply(503,['error'=>'Atualize o addon Evolution para habilitar a lista.']);
 $method=$_SERVER['REQUEST_METHOD']??'GET';
 if($method!=='GET'&&$method!=='POST')picker_reply(405,['error'=>'Metodo nao permitido.']);
 if(empty($_SESSION['evolution_picker_csrf']))$_SESSION['evolution_picker_csrf']=bin2hex(random_bytes(32));
 $csrf=$_SESSION['evolution_picker_csrf'];
 if($method==='POST'&&!hash_equals($csrf,(string)($_POST['csrf']??'')))picker_reply(403,['error'=>'Sessao do seletor expirada. Abra a lista novamente.']);
 session_write_close();
 $url='http://127.0.0.1:'.$config['port'].'/instance/fetchInstances';
 if(function_exists('curl_init')){
  $ch=curl_init($url);curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_CONNECTTIMEOUT=>3,CURLOPT_TIMEOUT=>8,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_PROXY=>'',CURLOPT_HTTPHEADER=>['apikey: '.$config['api_key']]]);$raw=curl_exec($ch);$status=curl_getinfo($ch,CURLINFO_HTTP_CODE);curl_close($ch);
 }else{
  $ctx=stream_context_create(['http'=>['method'=>'GET','header'=>'apikey: '.$config['api_key']."\r\n",'timeout'=>8,'follow_location'=>0,'ignore_errors'=>true]]);$raw=@file_get_contents($url,false,$ctx);$status=isset($http_response_header[0])&&preg_match('/^HTTP\/\S+ 200 /',$http_response_header[0])?200:0;
 }
 $rows=is_string($raw)?json_decode($raw,true):null;
 if($status!==200||!is_array($rows))picker_reply(502,['error'=>'Nao foi possivel consultar a Evolution local. Verifique Docker e API.']);
 $instances=[];
 foreach($rows as $row){
  if(!is_array($row)||!isset($row['name'])||!is_string($row['name']))continue;
  if(($row['integration']??'WHATSAPP-BAILEYS')!=='WHATSAPP-BAILEYS')continue;
  $state=$row['connectionStatus']??'unknown';
  if($method==='POST'&&$row['name']===($_POST['name']??'')){
   if(empty($row['token'])||!is_string($row['token']))picker_reply(409,['error'=>'A API nao disponibilizou a chave desta instancia.']);
   picker_reply(200,['address'=>$config['address'],'name'=>$row['name'],'token'=>$row['token'],'state'=>$state]);
  }
  $instances[]=['name'=>$row['name'],'state'=>$state];
 }
 if($method==='POST')picker_reply(404,['error'=>'Instancia nao encontrada. Atualize a lista.']);
 picker_reply(200,['instances'=>$instances,'csrf'=>$csrf]);
}
if(!is_array($config)||!preg_match('/^[a-f0-9]{64}$/',$config['secret']??'')){http_response_code(503);exit('Addon ainda nao configurado. Execute o instalador.');}
$expiry=(string)(time()+180);$nonce=bin2hex(random_bytes(16));$token=$expiry.'.'.$nonce;
$token.='.'.hash_hmac('sha256',$token,$config['secret']);
$secure=!empty($_SERVER['HTTPS'])&&$_SERVER['HTTPS']!=='off';
header('Set-Cookie: vpscloud_evolution_bridge='.$token.'; Max-Age=180; Path=/admin/addons/evolution/; HttpOnly; SameSite=Strict'.($secure?'; Secure':''),false);
header('Cache-Control: no-store');header('X-Frame-Options: SAMEORIGIN');
if(isset($_GET['refresh'])){header('Content-Type: application/json');echo '{"ok":true}';exit;}
$view=($_GET['view']??'')==='monitor'?'monitor/':'manager/';
session_write_close();
?><!doctype html><html lang="pt-BR" class="has-navbar-fixed-top"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evolution · MK-AUTH</title><link rel="stylesheet" href="../../estilos/mk-auth.css"><script src="../../scripts/jquery.js"></script><script src="../../scripts/mk-auth.js"></script><style>.evolution-addon{padding:22px 16px}nav.evolution-tabs{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:12px 0}.evolution-tabs a,.evolution-tabs button{padding:10px 16px;background:#168664;color:white;border-radius:6px;text-decoration:none}.evolution-addon iframe{width:100%;height:calc(100vh - 230px);min-height:600px;border:0;border-radius:8px;background:#08120f}.evolution-addon p{margin:8px 0;color:#395469}#session-error{color:#a42c28;font-weight:bold}</style></head><body>
<?php include '../../topo.php';include '../../menu.php'; ?>
<main class="evolution-addon"><h1>Evolution API</h1><nav class="evolution-tabs"><a href="?view=manager">Manager</a><a href="?view=monitor">Alertas Telegram</a><a href="../../conf_zap_serv.hhvm?vpscloud_evolution=1">Configurar servidor WhatsApp</a><button type="button" id="show-global-key">Ver chave global</button></nav><p>Use a API Key Global para entrar no Manager e no monitor. O acesso usa o mesmo endereco web do MK-AUTH.</p><p id="session-error" role="alert"></p><iframe title="Evolution" src="app/<?php echo $view; ?>" referrerpolicy="same-origin"></iframe></main>
<script>setInterval(async()=>{try{const r=await fetch('index.php?refresh=1',{credentials:'same-origin',cache:'no-store'});const o=await r.json();if(!r.ok||!o.ok)throw Error();}catch{document.getElementById('session-error').textContent='Sessao expirada. Entre novamente pelo MK-AUTH e reabra o addon.';}},90000);</script>
<script>
document.getElementById('show-global-key').onclick=async function(){
 const dialog=document.createElement('dialog');dialog.setAttribute('aria-label','Ver chave global');dialog.style.cssText='width:min(480px,90vw);padding:24px;border:1px solid #bdd3df;border-radius:10px';
 const title=document.createElement('h2');title.textContent='Ver chave global';
 const message=document.createElement('p');message.setAttribute('role','status');message.textContent='Confirmando sua sessão…';
 const form=document.createElement('form');const label=document.createElement('label');label.textContent='Sua senha do MK-AUTH';
 const password=document.createElement('input');password.type='password';password.autocomplete='current-password';password.required=true;password.style.cssText='display:block;width:100%;margin:10px 0;padding:10px';label.append(password);
 const submit=document.createElement('button');submit.type='submit';submit.disabled=true;submit.textContent='Confirmar senha e mostrar';submit.style.padding='10px';form.onsubmit=event=>event.preventDefault();
 const result=document.createElement('div');const key=document.createElement('input');key.readOnly=true;key.setAttribute('aria-label','Chave global');key.style.cssText='width:100%;padding:10px;margin:10px 0';
 const copy=document.createElement('button');copy.type='button';copy.textContent='Copiar chave';copy.onclick=async()=>{try{await navigator.clipboard.writeText(key.value);message.textContent='Chave copiada. Ela será ocultada ao completar 30 segundos.';}catch{key.select();message.textContent='Selecione a chave e copie com Ctrl+C.';}};
 result.append(key,copy);result.hidden=true;const close=document.createElement('button');close.type='button';close.textContent='Fechar';close.style.margin='12px';close.onclick=()=>dialog.close();
 let timer,csrf='';dialog.onclose=()=>{clearTimeout(timer);password.value='';key.value='';dialog.remove();};form.append(label,submit);dialog.append(title,message,form,result,close);document.body.append(dialog);dialog.showModal();password.focus();
 const endpoint='index.php?globalkey=1';
 async function request(options){const r=await fetch(endpoint,{credentials:'same-origin',cache:'no-store',...options});let body;try{body=await r.json();}catch{throw Error('Entre novamente pelo MK-AUTH e reabra o addon.');}if(!r.ok)throw Error(body.error||'Falha ao confirmar a senha.');return body;}
 try{const body=await request();csrf=body.csrf;submit.disabled=false;if(dialog.isConnected)message.textContent='Confirme a senha de '+body.user+'. A chave ficará visível por 30 segundos.';}catch(error){message.textContent=error.message;submit.disabled=true;}
 form.onsubmit=async event=>{event.preventDefault();if(!csrf)return;submit.disabled=true;message.textContent='Validando senha…';
  try{const body=await request({method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrf,password:password.value})});password.value='';if(!dialog.isConnected)return;key.value=body.key;form.hidden=true;result.hidden=false;message.textContent='Chave global. Será ocultada em 30 segundos.';timer=setTimeout(()=>dialog.close(),30000);}
  catch(error){password.value='';message.textContent=error.message;submit.disabled=false;password.focus();}
 };
};
</script>
<?php include '../../baixo.php'; ?></body></html>
