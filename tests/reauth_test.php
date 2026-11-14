<?php
require __DIR__.'/../addon/evolution/reauth.php';
function check($value,$message){if(!$value)throw new RuntimeException($message);}
$dir=sys_get_temp_dir().'/evolution-reauth-'.bin2hex(random_bytes(8));mkdir($dir,0700);
try{
 $hash=password_hash('correct-password',PASSWORD_BCRYPT);$users=['current'=>['sha'=>$hash,'ativo'=>'sim'],'disabled'=>['sha'=>$hash,'ativo'=>'nao']];
 $lookup=function($login)use($users){return $users[$login]??null;};
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
