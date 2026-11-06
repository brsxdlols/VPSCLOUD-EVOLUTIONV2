<?php
// VPSCloud receipt integration. PHP 7.1 compatible. No schema changes on HTTP.
define('RECIBO_DATA', getenv('RECIBO_DATA_DIR') ?: '/opt/mk-auth/dados/Recibo_Evolution');
function recibo_auth() {
    if (session_status() !== PHP_SESSION_ACTIVE) { session_name('mka'); session_start(); }
    if (empty($_SESSION['mka_logado']) && empty($_SESSION['MKA_Logado'])) {
        recibo_json(array('error'=>'Sessao expirada ou acesso negado. Entre novamente pelo MK-AUTH e atualize a pagina.'),401);
    }
    if (empty($_SESSION['recibo_csrf'])) $_SESSION['recibo_csrf'] = bin2hex(random_bytes(24));
}
function recibo_post() {
    recibo_auth();
    if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !hash_equals($_SESSION['recibo_csrf'], isset($_POST['csrf']) ? $_POST['csrf'] : '')) {
        recibo_json(array('error'=>'Requisicao invalida. Atualize a pagina.'),403);
    }
}
function recibo_json($value, $status = 200) { http_response_code($status); header('Content-Type: application/json; charset=utf-8'); echo json_encode($value, JSON_UNESCAPED_UNICODE); exit; }
function recibo_defaults() {
    return array('api_url'=>'http://127.0.0.1:7070','instance'=>'MKAUTH','token'=>'','provider'=>'Seu provedor','enabled'=>false,'interval'=>5,'retention_days'=>0,
        'template'=>"💵 *CONFIRMAÇÃO DE PAGAMENTO*\n\n👤 *Cliente*: {cliente}\n📄 *ID do pagamento*: {id_pagamento}\n📑 *CPF/CNPJ*: {cpf_cnpj}\n✅ *Pagamento recebido em*: {data_pagamento}\n📅 *Vencimento*: {data_vencimento}\n💰 *Valor da fatura*: R$ {valor}\n💸 *Valor pago*: R$ {valor_pago}\n👤 *Recebido por*: {coletor}\n💳 *Forma de pagamento*: {forma_pagamento}\n\n*Atenciosamente, {provedor}* 🤝\n_Mensagem gerada automaticamente pelo sistema._");
}
function recibo_native_connection($items) {
    if (($items['wapp_servidor'] ?? '')!=='evolution2_api') throw new Exception('O servidor WhatsApp do MK-AUTH deve estar configurado como Evolution2 API.');
    $url=trim($items['wapp_host'] ?? '');if(strpos($url,'://')===false)$url='http://'.$url;
    $u=parse_url($url);$instance=trim($items['wapp_login'] ?? '');$token=trim($items['wapp_pass'] ?? '');
    if(!$u || empty($u['host']) || !in_array($u['scheme'] ?? '',array('http','https'),true) || isset($u['user']) || isset($u['pass']) || preg_match('/[\r\n]/',$url.$token) || !$instance || strlen($instance)>100 || !$token)throw new Exception('Servidor WhatsApp incompleto ou invalido no MK-AUTH.');
    return array('api_url'=>rtrim($url,'/'),'instance'=>$instance,'token'=>$token);
}
function recibo_settings() {
    $p=RECIBO_DATA.'/settings.json'; $s=is_file($p)?json_decode(file_get_contents($p),true):array();
    return array_merge(recibo_defaults(), is_array($s)?$s:array());
}
function recibo_save($settings) {
    $p=RECIBO_DATA.'/settings.json'; $tmp=$p.'.'.bin2hex(random_bytes(6)).'.tmp';
    $raw=json_encode($settings, JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT);
    if (file_put_contents($tmp,$raw,LOCK_EX)===false) throw new Exception('Nao foi possivel gravar as configuracoes.');
    chmod($tmp,0660); if (!rename($tmp,$p)) { unlink($tmp); throw new Exception('Falha ao salvar configuracoes.'); }
}
function recibo_db() {
    $path=RECIBO_DATA.'/database.php'; if (!is_file($path)) throw new Exception('Addon ainda nao instalado. Execute o instalador.');
    $c=include($path); mysqli_report(MYSQLI_REPORT_OFF); $db=mysqli_init();
    $db->options(MYSQLI_OPT_CONNECT_TIMEOUT,3);
    if (!@$db->real_connect($c['host'],$c['user'],$c['password'],$c['name'])) throw new Exception('Banco indisponivel. Verifique o servico.');
    $db->set_charset('utf8mb4'); return $db;
}
function recibo_log($id, $event) {
    $line=date('Y-m-d H:i:s').' id='.(int)$id.' '.preg_replace('/[^a-zA-Z0-9_:= .-]/','',substr($event,0,200))."\n";
    $p=RECIBO_DATA.'/log_pagamentos.txt';$new=!file_exists($p);file_put_contents($p,$line,FILE_APPEND|LOCK_EX);if($new)@chmod($p,0660);
}
function recibo_tail($file, $bytes=65536) {
    if (!is_file($file)) return 'Ainda sem registros de execucao.';
    $f=fopen($file,'rb'); if (!$f) return 'Log indisponivel.';
    $size=filesize($file); if ($size>$bytes) { fseek($f,-$bytes,SEEK_END); fgets($f); }
    $text=stream_get_contents($f,$bytes); fclose($f); return $text;
}
function recibo_phone($value) {
    $n=preg_replace('/\D/','',$value); if (strlen($n)===10 || strlen($n)===11) $n='55'.$n;
    return preg_match('/^[1-9][0-9]{11,14}$/',$n)?$n:'';
}
function recibo_render($template, $values) {
    $out=array(); foreach($values as $key=>$value) $out['{'.$key.'}']=(string)$value;
    return strtr($template,$out);
}
function recibo_values($row,$s) {
    $doc=preg_replace('/\D/','',$row['cpf_cnpj']);
    if (strlen($doc)===11) $doc=preg_replace('/(\d{3})(\d{3})(\d{3})(\d{2})/','$1.$2.$3-$4',$doc);
    elseif (strlen($doc)===14) $doc=preg_replace('/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/','$1.$2.$3/$4-$5',$doc);
    return array('cliente'=>$row['nome'],'cpf_cnpj'=>$doc,'id_pagamento'=>$row['id'],
        'data_pagamento'=>date('d/m/Y',strtotime($row['datapag'])),'data_vencimento'=>date('d/m/Y',strtotime($row['datavenc'])),
        'valor'=>number_format($row['valor'],2,',','.'),'valor_pago'=>number_format($row['valorpag'],2,',','.'),
        'coletor'=>$row['coletor'],'forma_pagamento'=>$row['formapag'],'provedor'=>$s['provider']);
}
function recibo_http($s,$path,$payload=null) {
    $ch=curl_init(rtrim($s['api_url'],'/').$path);
    curl_setopt_array($ch,array(CURLOPT_RETURNTRANSFER=>true,CURLOPT_CONNECTTIMEOUT=>3,CURLOPT_TIMEOUT=>8,
        CURLOPT_FOLLOWLOCATION=>false,CURLOPT_HTTPHEADER=>array('Content-Type: application/json','apikey: '.$s['token'])));
    if ($payload!==null) { curl_setopt($ch,CURLOPT_POST,true); curl_setopt($ch,CURLOPT_POSTFIELDS,json_encode($payload,JSON_UNESCAPED_UNICODE)); }
    $body=curl_exec($ch); $code=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE); $error=curl_errno($ch); curl_close($ch);
    return array('http'=>$code,'error'=>$error,'body'=>json_decode($body?:'',true));
}
function recibo_outcome($r) {
    if (!$r['error'] && in_array($r['http'],array(200,201),true) && !empty($r['body']['key']['id'])) return 1;
    if (!$r['error'] && $r['http']>=400 && $r['http']<500 && $r['http']!==408) return 3;
    return 2; // Timeout/ambiguous acceptance: require operator review, never resend automatically.
}
function recibo_discard_pending($db) {
    $lock=$db->query("SELECT GET_LOCK('vpscloud_recibo_evolution',0) AS acquired");
    if(!$lock || (int)$lock->fetch_assoc()['acquired']!==1) throw new Exception('Ha um envio em andamento. Aguarde e tente novamente.');
    try {
        if(!$db->query('UPDATE brl_pago SET envio=4 WHERE envio=0')) throw new Exception('Nao foi possivel descartar os pendentes.');
        return $db->affected_rows;
    } finally { $db->query("SELECT RELEASE_LOCK('vpscloud_recibo_evolution')"); }
}
function recibo_run($db,$manual=false,$limit=5) {
    $s=recibo_settings(); if (!$manual && !$s['enabled']) return array('status'=>'paused','message'=>'Envio automatico desativado.','sent'=>0);
    if (empty($s['token']) || empty($s['api_url']) || empty($s['instance'])) throw new Exception('Configure a API e a instancia primeiro.');
    $lock=$db->query("SELECT GET_LOCK('vpscloud_recibo_evolution',0) AS acquired");
    if (!$lock || (int)$lock->fetch_assoc()['acquired']!==1) return array('status'=>'busy','message'=>'Outra execucao ja esta em andamento.','sent'=>0);
    try {
        $last=RECIBO_DATA.'/last-run';
        if (!$manual && is_file($last) && time()-(int)file_get_contents($last)<max(1,(int)$s['interval'])*60) return array('status'=>'waiting','sent'=>0,'message'=>'Aguardando intervalo.');
        file_put_contents($last,(string)time(),LOCK_EX); @chmod($last,0660);
        $health=recibo_http($s,'/instance/connectionState/'.rawurlencode($s['instance']));
        if ($health['http']!==200 || empty($health['body']['instance']['state']) || $health['body']['instance']['state']!=='open') {
            recibo_log(0,'PAUSED_INSTANCE_NOT_OPEN'); return array('status'=>'paused','sent'=>0,'message'=>'Instancia desconectada ou API indisponivel. Nenhum recibo enviado.');
        }
        $limit=max(1,min(20,(int)$limit));
        $sql="SELECT p.*, c.nome, c.celular, c.cpf_cnpj, c.zap, c.cli_ativado FROM brl_pago p LEFT JOIN sis_cliente c ON c.login=p.login WHERE p.envio=0 ORDER BY p.id LIMIT ".$limit;
        $rows=$db->query($sql); if (!$rows) throw new Exception('Fila indisponivel. Verifique a instalacao.');
        $start=time();$sent=0;$review=0;$failed=0;
        while ($row=$rows->fetch_assoc()) {
            if (time()-$start>=40) break;
            $id=(int)$row['id'];$phone=recibo_phone($row['celular']?:'');
            if (!$phone || $row['zap']==='nao' || $row['cli_ativado']==='n' || !$row['nome']) {
                $db->query("UPDATE brl_pago SET envio=3 WHERE id=$id AND envio=0");recibo_log($id,'SKIPPED_CONTACT_OR_PREFERENCE');$failed++;continue;
            }
            // Persist the claim before the HTTP request. A crash cannot cause blind retry.
            if (!$db->query("UPDATE brl_pago SET envio=2 WHERE id=$id AND envio=0") || $db->affected_rows!==1) continue;
            $message=recibo_render($s['template'],recibo_values($row,$s));
            $r=recibo_http($s,'/message/sendText/'.rawurlencode($s['instance']),array('number'=>$phone,'text'=>$message));
            $status=recibo_outcome($r);$messageId=$status===1?(string)$r['body']['key']['id']:'';
            $q=$db->prepare('INSERT INTO vpscloud_recibo_delivery(queue_id,status,http_code,message_id,updated_at) VALUES(?,?,?,?,NOW()) ON DUPLICATE KEY UPDATE status=VALUES(status),http_code=VALUES(http_code),message_id=VALUES(message_id),updated_at=NOW()');
            if ($q) { $q->bind_param('iiis',$id,$status,$r['http'],$messageId);$q->execute();$q->close(); }
            if (!$db->query("UPDATE brl_pago SET envio=$status WHERE id=$id AND envio=2")) { recibo_log($id,'REVIEW_DATABASE_UPDATE');$review++;continue; }
            recibo_log($id,'STATUS='.$status.' HTTP='.$r['http'].' CURL='.$r['error']);
            if ($status===1) $sent++; elseif ($status===2) $review++; else $failed++;
        }
        return array('status'=>'done','sent'=>$sent,'review'=>$review,'failed'=>$failed,'message'=>"Aceitos pela API: $sent. Revisao: $review. Falhas: $failed. Confirme a entrega no destinatario.");
    } finally { $db->query("SELECT RELEASE_LOCK('vpscloud_recibo_evolution')"); }
}
