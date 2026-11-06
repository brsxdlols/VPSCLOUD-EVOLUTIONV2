<?php
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
    if ($action==='preview') {
        $s=recibo_settings();$sample=array('cliente'=>'Cliente de exemplo','cpf_cnpj'=>'000.000.000-00','id_pagamento'=>'123','data_pagamento'=>date('d/m/Y'),'data_vencimento'=>date('d/m/Y'),'valor'=>'100,00','valor_pago'=>'100,00','coletor'=>'Atendimento','forma_pagamento'=>'PIX','provedor'=>$s['provider']);
        recibo_json(array('preview'=>recibo_render(substr($_POST['template'],0,10000),$sample)));
    }
    if ($action==='run') { session_write_close();$db=recibo_db();$out=recibo_run($db,true,1);$db->close();recibo_json($out); }
    if ($action==='clear_log') { file_put_contents(RECIBO_DATA.'/log_pagamentos.txt','',LOCK_EX);recibo_json(array('message'=>'Log limpo. A rotacao automatica continua ativa.')); }
    if ($action==='retry') {
        if (empty($_POST['confirm_retry'])) throw new Exception('Confirme a revisao do envio anterior.');
        $db=recibo_db();$id=(int)$_POST['id'];$q=$db->prepare('UPDATE brl_pago SET envio=0 WHERE id=? AND envio IN (2,3)');$q->bind_param('i',$id);$q->execute();$q->close();$db->close();recibo_log($id,'MANUAL_REQUEUE');recibo_json(array('message'=>'Registro recolocado na fila por solicitacao do operador.'));
    }
    throw new Exception('Acao nao reconhecida.');
} catch (Exception $e) { recibo_json(array('error'=>$e->getMessage()),400); }
