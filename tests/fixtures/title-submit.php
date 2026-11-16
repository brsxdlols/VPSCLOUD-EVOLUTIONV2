<?php
// Disposable CI only: calls the fake local API, never a real WhatsApp backend.
function ci_send($route,$body){
 $c=curl_init('http://127.0.0.1:7070'.$route);curl_setopt_array($c,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_POST=>true,CURLOPT_POSTFIELDS=>json_encode($body),CURLOPT_HTTPHEADER=>['Content-Type: application/json','apikey: ci-only-global-key']]);$raw=curl_exec($c);$status=curl_getinfo($c,CURLINFO_HTTP_CODE);curl_close($c);if($status!==200)throw new RuntimeException('Fake API rejected request: '.$status);return json_decode($raw,true);
}
$out=['titles'=>$_POST['destino']??[],'messages'=>[]];
if(($_SERVER['REQUEST_METHOD']??'')==='POST'){
 $caption=str_replace('%cliente%','CI Recipient',$_POST['texto_wapp']??'');
 $out['messages'][]=ci_send('/message/sendText/CI_ONLY_NO_PHONE',['number'=>'5511999999999','text'=>$caption]);
 if(($_POST['envia_pdf']??'')==='sim')$out['messages'][]=ci_send('/message/sendMedia/CI_ONLY_NO_PHONE',['number'=>'5511999999999','mediatype'=>'document','mimetype'=>'application/pdf','media'=>'ci-only-pdf','fileName'=>'boleto.pdf']);
}
?><!doctype html><meta charset="utf-8"><pre id="result"><?=htmlspecialchars(json_encode($out),ENT_QUOTES,'UTF-8')?></pre>
