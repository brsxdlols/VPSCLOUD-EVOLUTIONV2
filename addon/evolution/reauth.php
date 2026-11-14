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
        if(!is_array($state)||($state['until']??0)<=$now||($state['scheme']??'')!=='native-sha256-bcrypt')$state=['until'=>$now+900,'attempts'=>0,'scheme'=>'native-sha256-bcrypt'];
        if(($state['attempts']??0)>=5)throw new RuntimeException('Muitas tentativas. Aguarde 15 minutos e tente novamente.',429);
        $state['attempts']++;
        rewind($handle);ftruncate($handle,0);fwrite($handle,json_encode($state));fflush($handle);
        $row=$lookup($login);
        // Native MK-AUTH login sends SHA-256(password) to its bcrypt verifier.
        $valid=is_array($row)&&($row['ativo']??'')==='sim'&&is_string($row['sha']??null)&&password_verify(hash('sha256',$password),$row['sha']);
        if($valid){rewind($handle);ftruncate($handle,0);fwrite($handle,json_encode(['until'=>$now+900,'attempts'=>0,'scheme'=>'native-sha256-bcrypt']));fflush($handle);}
        return $valid;
    }finally{flock($handle,LOCK_UN);fclose($handle);}
}
