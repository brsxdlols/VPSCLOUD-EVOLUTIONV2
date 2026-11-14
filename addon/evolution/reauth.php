<?php
// Passwords and API keys are never persisted in the attempt counter.
function evolution_reauth($login,$password,$directory,$lookup,$now=null){
    $now=$now===null?time():$now;
    if(!is_string($login)||$login===''||strlen($login)>255||!is_string($password)||$password===''||strlen($password)>1024)return false;
    $path=$directory.'/'.hash('sha256',$login).'.json';
    $handle=@fopen($path,'c+');
    if(!$handle||!flock($handle,LOCK_EX)){if($handle)fclose($handle);throw new RuntimeException('Nao foi possivel validar a senha.',503);}
    try{
        $state=json_decode(stream_get_contents($handle),true);
        if(!is_array($state)||($state['until']??0)<=$now)$state=['until'=>$now+900,'attempts'=>0];
        if(($state['attempts']??0)>=5)throw new RuntimeException('Muitas tentativas. Aguarde 15 minutos e tente novamente.',429);
        $state['attempts']++;
        rewind($handle);ftruncate($handle,0);fwrite($handle,json_encode($state));fflush($handle);
        $row=$lookup($login);
        $valid=is_array($row)&&($row['ativo']??'')==='sim'&&is_string($row['sha']??null)&&password_verify($password,$row['sha']);
        if($valid){rewind($handle);ftruncate($handle,0);fwrite($handle,json_encode(['until'=>$now+900,'attempts'=>0]));fflush($handle);}
        return $valid;
    }finally{flock($handle,LOCK_UN);fclose($handle);}
}
