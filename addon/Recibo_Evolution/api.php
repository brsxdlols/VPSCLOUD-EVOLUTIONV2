<?php
// Use the same native MK-AUTH session bootstrap as the addon page.
ob_start();
$reciboBootComplete=false;
register_shutdown_function(function()use(&$reciboBootComplete){if(!$reciboBootComplete){while(ob_get_level())ob_end_clean();http_response_code(401);header('Content-Type: application/json; charset=utf-8');echo json_encode(array('error'=>'Sessao expirada ou acesso negado. Entre novamente pelo MK-AUTH.'));}});
include __DIR__.'/addons.class.php';
$reciboBootComplete=true;
ob_end_clean();
require_once __DIR__.'/common.php';recibo_post();
try {
    $action=isset($_POST['action'])?$_POST['action']:'';
    if ($action==='save') {
        $s=recibo_settings();$url=trim($_POST['api_url']);$u=parse_url($url);
        if (!$u || !isset($u['scheme'],$u['host']) || !in_array($u['scheme'],array('http','https'),true) || isset($u['user']) || isset($u['pass']) || preg_match('/[\r\n]/',$url)) throw new Exception('URL da API invalida.');
        $instance=trim($_POST['instance']);if (!$instance || strlen($instance)>100) throw new Exception('Nome da instancia invalido.');
        $template=trim($_POST['template']);if (!$template || strlen($template)>10000) throw new Exception('Template obrigatorio, com ate 10000 bytes.');
        $s['api_url']=rtrim($url,'/');$s['instance']=$instance;$s['provider']=trim($_POST['provider']);$s['enabled']=!empty($_POST['enabled']);$s['interval']=max(1,min(60,(int)$_POST['interval']));$s['template']=$template;
        if (trim($_POST['token'])!=='') $s['token']=trim($_POST['token']);
        if (preg_match('/[\r\n]/',$s['token'])) throw new Exception('Token invalido.');
        recibo_save($s);recibo_json(array('message'=>'Configuracao e template salvos.'));
    }
    if ($action==='import_native') {
        $db=recibo_db();$q=$db->query('SELECT nome,valor FROM vpscloud_recibo_whatsapp');
        if(!$q){$db->close();throw new Exception('Importacao ainda nao instalada. Atualize o addon pelo instalador.');}
        $items=array();while($r=$q->fetch_assoc())$items[$r['nome']]=$r['valor'];$db->close();
        $connection=recibo_native_connection($items);$s=recibo_settings();
        foreach($connection as $k=>$v)$s[$k]=$v;recibo_save($s);
        recibo_json(array('message'=>'Conexao do WhatsApp do MK-AUTH importada e salva. Envio automatico nao foi alterado.','api_url'=>$s['api_url'],'instance'=>$s['instance']));
    }
    if ($action==='preview') {
        $s=recibo_settings();$sample=array('cliente'=>'Cliente de exemplo','cpf_cnpj'=>'000.000.000-00','id_pagamento'=>'123','data_pagamento'=>date('d/m/Y'),'data_vencimento'=>date('d/m/Y'),'valor'=>'100,00','valor_pago'=>'100,00','coletor'=>'Atendimento','forma_pagamento'=>'PIX','provedor'=>$s['provider']);
        recibo_json(array('preview'=>recibo_render(substr($_POST['template'],0,10000),$sample)));
    }
    if ($action==='simulate_next' || $action==='simulate_discard') {
        $db=recibo_db();try{
            if($action==='simulate_next')$message=recibo_simulate_next($db);
            else{$count=recibo_simulate_discard($db,$_POST['scope'] ?? 'all');$message="Simulacao: $count pendentes seriam descartados. Nenhum registro foi alterado e nenhuma mensagem foi enviada.";}
        }finally{$db->close();}recibo_json(array('message'=>$message));
    }
    if ($action==='send_test') {
        if(($_POST['confirm_test'] ?? '')!=='ENVIAR_TESTE')throw new Exception('Confirme o envio de teste.');
        $phone=recibo_phone($_POST['test_phone'] ?? '');if(!$phone)throw new Exception('Informe o numero de teste com DDD e DDI.');
        if(time()-(int)($_SESSION['recibo_last_test'] ?? 0)<60)throw new Exception('Aguarde 60 segundos antes de outro teste.');
        $s=recibo_settings();if(!$s['token'])throw new Exception('Salve a conexao primeiro.');
        $_SESSION['recibo_last_test']=time();session_write_close();
        $health=recibo_http($s,'/instance/connectionState/'.rawurlencode($s['instance']));
        if($health['http']!==200 || ($health['body']['instance']['state'] ?? '')!=='open')throw new Exception('Instancia desconectada ou API indisponivel. Teste nao enviado.');
        $out=recibo_http($s,'/message/sendText/'.rawurlencode($s['instance']),array('number'=>$phone,'text'=>recibo_test_message($s)));
        $status=recibo_outcome($out);
        recibo_json(array('message'=>$status===1?'Teste aceito pela API. Confira no numero informado. A fila de recibos nao foi alterada.':($status===2?'Resultado incerto. Confira o numero de teste antes de repetir. A fila nao foi alterada.':'Teste recusado pela API. Confira a conexao. A fila nao foi alterada.')));
    }
    if ($action==='run') { session_write_close();$db=recibo_db();$out=recibo_run($db,true,1);$db->close();recibo_json($out); }
    if ($action==='discard_pending') {
        if (($_POST['confirm_discard'] ?? '')!=='DESCARTAR') throw new Exception('Confirme o descarte dos pendentes.');
        session_write_close();$db=recibo_db();
        try{$count=recibo_discard_pending($db,$_POST['scope'] ?? 'all');}finally{$db->close();}
        recibo_log(0,'MANUAL_DISCARD_PENDING COUNT='.$count);
        recibo_json(array('message'=>"Pendentes descartados sem envio: $count. Historico preservado.",'discarded'=>$count));
    }
    if ($action==='clear_log') { file_put_contents(RECIBO_DATA.'/log_pagamentos.txt','',LOCK_EX);recibo_json(array('message'=>'Log limpo. A rotacao automatica continua ativa.')); }
    if ($action==='retry') {
        if (empty($_POST['confirm_retry'])) throw new Exception('Confirme a revisao do envio anterior.');
        $db=recibo_db();$id=(int)$_POST['id'];$q=$db->prepare('UPDATE brl_pago SET envio=0 WHERE id=? AND envio IN (2,3)');$q->bind_param('i',$id);$q->execute();$q->close();$db->close();recibo_log($id,'MANUAL_REQUEUE');recibo_json(array('message'=>'Registro recolocado na fila por solicitacao do operador.'));
    }
    throw new Exception('Acao nao reconhecida.');
} catch (Exception $e) { recibo_json(array('error'=>$e->getMessage()),400); }
