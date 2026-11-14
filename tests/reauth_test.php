<?php
require __DIR__.'/../addon/evolution/reauth.php';
function check($value,$message){if(!$value)throw new RuntimeException($message);}
$dir=sys_get_temp_dir().'/evolution-reauth-'.bin2hex(random_bytes(8));mkdir($dir,0700);
try{
 check(evolution_native_password_digest('senha-áé')==='81e4d5f102a0c12054a9ba197b24ed697eca125c23f3be71f24b1952133b7abd','Native accented password encoding differs');
 check(evolution_native_password_digest('senha-🔑')==='03653ed1e4a94d1c1810a0dfbfdb0759a8916c954d278b84fe3a58f4b4588e45','Native surrogate encoding differs');
 $hash=password_hash(hash('sha256','correct-password'),PASSWORD_BCRYPT);$users=['current'=>['sha'=>$hash,'ativo'=>'sim'],'disabled'=>['sha'=>$hash,'ativo'=>'nao']];
 $lookup=function($login)use($users){return $users[$login]??null;};
 file_put_contents($dir.'/'.hash('sha256','current').'.json',json_encode(['until'=>9999,'attempts'=>5]));
 check(evolution_reauth('current','correct-password',$dir,$lookup,99),'Old faulty-verifier attempts were not reset');
 check(!evolution_reauth('current','wrong',$dir,$lookup,100),'Wrong password accepted');
 check(evolution_reauth('current','correct-password',$dir,$lookup,101),'Correct password rejected');
 check(!evolution_reauth('disabled','correct-password',$dir,$lookup,101),'Disabled user accepted');
 check(!evolution_reauth('missing','correct-password',$dir,$lookup,101),'Missing user accepted');
 for($i=0;$i<5;$i++)check(!evolution_reauth('current','wrong',$dir,$lookup,102+$i),'Wrong password accepted');
 $limited=false;try{evolution_reauth('current','correct-password',$dir,$lookup,110);}catch(RuntimeException $e){$limited=$e->getCode()===429;}
 check($limited,'Limit missing across requests');check(evolution_reauth('current','correct-password',$dir,$lookup,1100),'Limit did not expire');
 foreach(glob($dir.'/*.json') as $file){$s=file_get_contents($file);check(strpos($s,'correct-password')===false&&strpos($s,$hash)===false,'Password persisted');}
 echo "PASS password verification, disabled users, shared attempt limit, expiry and no password storage\n";
}finally{foreach(glob($dir.'/*.json') as $file)unlink($file);rmdir($dir);}
