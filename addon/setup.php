<?php
// Root/CLI-only schema setup. Never installed as a public HTTP endpoint.
if(PHP_SAPI!=='cli'){http_response_code(403);exit;}
mysqli_report(MYSQLI_REPORT_OFF);
$input=json_decode(file_get_contents($argv[1]),true);
$root=$input['database'];$backup=$input['backup'];$data=$input['data'];
$db=new mysqli($root['host'],$root['user'],$root['password'],$root['name']);
if($db->connect_error){fwrite(STDERR,"Banco indisponivel.\n");exit(1);}
$db->set_charset('utf8mb4');
function rq($db,$sql){$r=$db->query($sql);if($r===false)throw new Exception('Falha na preparacao do addon; consulte o backup.');return $r;}
try {
    if(stripos($db->server_info,'MariaDB')===false)throw new Exception('Esta revisao exige MariaDB com CREATE OR REPLACE TRIGGER.');
    foreach(array('sis_lanc'=>array('id','login','status','coletor','datavenc','datapag','valor','valorpag','formapag'),'sis_cliente'=>array('login','nome','celular','cpf_cnpj','zap','cli_ativado')) as $table=>$columns){
        $found=array();$r=rq($db,'SHOW COLUMNS FROM `'.$table.'`');while($x=$r->fetch_assoc())$found[]=$x['Field'];
        if(array_diff($columns,$found))throw new Exception('Estrutura MK-AUTH nao reconhecida: '.$table);
    }
    $old=null;$r=rq($db,"SELECT ACTION_STATEMENT,EVENT_OBJECT_TABLE,ACTION_TIMING,EVENT_MANIPULATION FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND TRIGGER_NAME='tig_brl_pag'");
    if($r->num_rows){$old=$r->fetch_assoc();if($old['EVENT_OBJECT_TABLE']!=='sis_lanc'||$old['ACTION_TIMING']!=='AFTER'||$old['EVENT_MANIPULATION']!=='UPDATE'||stripos($old['ACTION_STATEMENT'],'brl_pago')===false)throw new Exception('Trigger existente personalizada. Intervencao manual necessaria.');}
    file_put_contents($backup.'/trigger-before.json',json_encode($old,JSON_PRETTY_PRINT));
    if($old){$raw=rq($db,'SHOW CREATE TRIGGER tig_brl_pag')->fetch_assoc();file_put_contents($backup.'/trigger-create-before.json',json_encode($raw,JSON_PRETTY_PRINT));}
    $exists=rq($db,"SHOW TABLES LIKE 'brl_pago'")->num_rows;
    if($exists){
        $create=rq($db,'SHOW CREATE TABLE brl_pago')->fetch_assoc();file_put_contents($backup.'/brl-schema.json',json_encode($create));
        $dump=fopen($backup.'/brl-rows.sql','wb');if(!$dump)throw new Exception('Falha ao abrir backup da fila.');$r=$db->query('SELECT * FROM brl_pago',MYSQLI_USE_RESULT);if(!$r)throw new Exception('Falha ao ler fila para backup.');
        while($row=$r->fetch_assoc()){$names=array();$values=array();foreach($row as $k=>$v){$names[]='`'.str_replace('`','``',$k).'`';$values[]=$v===null?'NULL':"'".$db->real_escape_string($v)."'";}if(fwrite($dump,'INSERT INTO brl_pago('.implode(',',$names).') VALUES('.implode(',',$values).");\n")===false)throw new Exception('Falha ao gravar backup da fila.');}$r->free();if(!fclose($dump))throw new Exception('Falha ao concluir backup da fila.');
    }
    rq($db,"CREATE TABLE IF NOT EXISTS brl_pago (id INT NOT NULL PRIMARY KEY,data TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,login VARCHAR(64) NOT NULL,coletor VARCHAR(64),datavenc DATE,datapag DATETIME,valor DECIMAL(10,2),valorpag DECIMAL(10,2),formapag VARCHAR(32),envio TINYINT NOT NULL DEFAULT 0,INDEX recibo_envio_data(envio,data)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $columns=array();$r=rq($db,'SHOW COLUMNS FROM brl_pago');while($x=$r->fetch_assoc())$columns[]=$x['Field'];
    if(array_diff(array('id','data','login','coletor','datavenc','datapag','valor','valorpag','formapag','envio'),$columns))throw new Exception('Fila existente incompativel; nenhuma coluna sera removida.');
    rq($db,"CREATE TABLE IF NOT EXISTS vpscloud_recibo_delivery(queue_id INT NOT NULL PRIMARY KEY,status TINYINT NOT NULL,http_code INT NOT NULL DEFAULT 0,message_id VARCHAR(128) NOT NULL DEFAULT '',updated_at DATETIME NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $runtimeFile=$data.'/database.php';
    $runtimeUser=isset($input['runtime_user'])?$input['runtime_user']:'vpscloud_recibo';
    if(!preg_match('/^[a-zA-Z0-9_]{1,32}$/',$runtimeUser))throw new Exception('Nome de usuario dedicado invalido.');
    if(is_file($runtimeFile)){$runtime=include($runtimeFile);if($runtime['user']!==$runtimeUser)throw new Exception('Credencial local personalizada; revise antes de substituir.');}
    else {
        if(rq($db,"SELECT User FROM mysql.user WHERE User='".$runtimeUser."'")->num_rows)throw new Exception('Usuario de banco ja existe sem credencial local; nao sera sobrescrito.');
        $runtime=array('host'=>'127.0.0.1','user'=>$runtimeUser,'password'=>bin2hex(random_bytes(24)),'name'=>$root['name']);
    }
    $dbName='`'.str_replace('`','``',$root['name']).'`';
    foreach(array('localhost','127.0.0.1') as $host){$account="'".$runtimeUser."'@'".$host."'";
        rq($db,'CREATE USER IF NOT EXISTS '.$account." IDENTIFIED BY '".$db->real_escape_string($runtime['password'])."'");
        rq($db,'GRANT SELECT ON '.$dbName.'.sis_cliente TO '.$account);
        rq($db,'GRANT SELECT,UPDATE,DELETE ON '.$dbName.'.brl_pago TO '.$account);
        rq($db,'GRANT SELECT,INSERT,UPDATE,DELETE ON '.$dbName.'.vpscloud_recibo_delivery TO '.$account);
    }
    $test=new mysqli($runtime['host'],$runtime['user'],$runtime['password'],$runtime['name']);if($test->connect_error)throw new Exception('Falha ao validar usuario dedicado; trigger preservada.');$test->close();
    $body="BEGIN
IF NEW.status='pago' AND NOT(OLD.status <=> 'pago')
AND DATE(NEW.datapag)=DATE(NOW())
AND EXISTS(SELECT 1 FROM sis_cliente WHERE login=NEW.login AND zap<>'nao' AND cli_ativado<>'n') THEN
INSERT IGNORE INTO brl_pago(id,data,login,coletor,datavenc,datapag,valor,valorpag,formapag)
VALUES(NEW.id,NOW(),NEW.login,NEW.coletor,NEW.datavenc,NEW.datapag,NEW.valor,NEW.valorpag,NEW.formapag);
END IF;
END";
    if(!$old || trim($old['ACTION_STATEMENT'])!==trim($body)){
        if(!$db->query('CREATE OR REPLACE TRIGGER tig_brl_pag AFTER UPDATE ON sis_lanc FOR EACH ROW '.$body)){
            if($old)$db->query('CREATE OR REPLACE TRIGGER tig_brl_pag AFTER UPDATE ON sis_lanc FOR EACH ROW '.$old['ACTION_STATEMENT']);
            throw new Exception('Falha no trigger; definicao anterior preservada/tentada.');
        }
    }
    file_put_contents($runtimeFile,'<?php return '.var_export($runtime,true).';',LOCK_EX);chmod($runtimeFile,0640);
    echo "SCHEMA_READY: fila preservada, usuario dedicado e captura em transicao para pago.\n";
} catch(Exception $e){fwrite(STDERR,$e->getMessage()."\n");exit(1);}
