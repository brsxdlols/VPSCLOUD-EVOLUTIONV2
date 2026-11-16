<?php
function evolution_title_photo_request($config,$payload=null){
    $ch=curl_init('http://127.0.0.1:'.$config['port'].'/ops/title-photo');
    $headers=['apikey: '.$config['api_key']];$options=[CURLOPT_RETURNTRANSFER=>true,CURLOPT_CONNECTTIMEOUT=>3,CURLOPT_TIMEOUT=>10,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_PROXY=>''];
    if($payload!==null){$options[CURLOPT_POST]=true;$options[CURLOPT_POSTFIELDS]=json_encode($payload);$headers[]='Content-Type: application/json';}
    $options[CURLOPT_HTTPHEADER]=$headers;curl_setopt_array($ch,$options);$raw=curl_exec($ch);$status=curl_getinfo($ch,CURLINFO_HTTP_CODE);curl_close($ch);
    $body=is_string($raw)?json_decode($raw,true):null;
    if($status!==200||!is_array($body))throw new RuntimeException('Nao foi possivel preparar a foto. Atualize os auxiliares da Evolution e tente novamente.');
    return $body;
}
function evolution_title_photo($config){
    if(!is_array($config)||empty($config['api_key'])||empty($config['port'])||!function_exists('curl_init'))picker_reply(503,['error'=>'Atualize o addon Evolution para habilitar fotos.']);
    if(empty($_SESSION['evolution_title_csrf']))$_SESSION['evolution_title_csrf']=bin2hex(random_bytes(32));
    $method=$_SERVER['REQUEST_METHOD']??'GET';
    if($method!=='GET'&&$method!=='POST')picker_reply(405,['error'=>'Metodo nao permitido.']);
    if($method==='POST'&&(!is_string($_POST['csrf']??null)||!hash_equals($_SESSION['evolution_title_csrf'],$_POST['csrf'])))picker_reply(403,['error'=>'Sessao expirada. Reabra o envio.']);
    try{
        $connection=function(){ob_start();include_once '/opt/mk-auth/admin/config.php';ob_end_clean();return isset($conn)?$conn:($GLOBALS['conn']??null);};$db=$connection();
        if(!($db instanceof mysqli))throw new RuntimeException('Configuracao nativa indisponivel.');
        $q=$db->query("SELECT nome,valor FROM sis_opcao WHERE nome IN ('wapp_servidor','wapp_host','wapp_login','libzap')");if(!$q)throw new RuntimeException('Configuracao WhatsApp indisponivel.');
        $native=[];while($row=$q->fetch_assoc())$native[$row['nome']]=$row['valor'];
        $host=trim($native['wapp_host']??'');$url=parse_url(strpos($host,'://')===false?'http://'.$host:$host);
        $installed=parse_url('http://'.$config['address']);
        $v2=($native['wapp_servidor']??'')==='evolution2_api'||(($native['wapp_servidor']??'')==='evolution_api'&&($native['libzap']??'')==='/opt/mk-auth/libs/ZAP/evolution2.php');
        if(!$v2||!$url||($url['scheme']??'')!=='http'||isset($url['user'])||isset($url['pass'])||isset($url['query'])||isset($url['fragment'])||!in_array($url['path']??'',['','/'],true)||!in_array($url['host']??'',['127.0.0.1','localhost',$installed['host']],true)||($url['port']??80)!==$config['port']||empty($native['wapp_login']))throw new RuntimeException('Configure WhatsApp Servidor como Evolution2 API local para anexar fotos aos titulos.');
        if($method==='GET'){$ready=evolution_title_photo_request($config);if(empty($ready['ready']))throw new RuntimeException('Auxiliar de fotos indisponivel.');picker_reply(200,['csrf'=>$_SESSION['evolution_title_csrf'],'maxBytes'=>2*1024*1024]);}
        $file=$_FILES['photo']??[];
        if(($file['error']??-1)!==UPLOAD_ERR_OK||empty($file['tmp_name'])||!is_uploaded_file($file['tmp_name'])||($file['size']??0)>2*1024*1024)throw new RuntimeException('Selecione uma foto PNG, JPG ou GIF de ate 2 MiB.');
        $bytes=file_get_contents($file['tmp_name']);$image=@getimagesizefromstring($bytes);$mime=$image['mime']??'';
        if(!$image||!in_array($mime,['image/png','image/jpeg','image/gif'],true))throw new RuntimeException('Arquivo de imagem invalido.');
        $photo=evolution_title_photo_request($config,['media'=>base64_encode($bytes),'mimetype'=>$mime,'instance'=>$native['wapp_login']]);
        if(!preg_match('/^[a-f0-9]{48}$/',$photo['token']??''))throw new RuntimeException('Nao foi possivel preparar a foto.');
        picker_reply(200,['marker'=>'[VPSCLOUD_TITLE_PHOTO:'.$photo['token'].']']);
    }catch(RuntimeException $error){picker_reply(400,['error'=>$error->getMessage()]);}
}
