<?php
if(PHP_SAPI!=='cli')exit(1);
$tmp=sys_get_temp_dir().'/recibo-unit-'.bin2hex(random_bytes(6));mkdir($tmp,0700);putenv('RECIBO_DATA_DIR='.$tmp);
require __DIR__.'/Recibo_Evolution/common.php';
function check($ok,$name){if(!$ok){fwrite(STDERR,'FAIL '.$name."\n");exit(1);}echo 'PASS '.$name."\n";}
check(recibo_phone('(16) 98877-0000')==='5516988770000','normalize Brazilian mobile');
check(recibo_phone('16 3877-0000')==='551638770000','preserve landline length without inventing ninth digit');
check(recibo_phone('0')==='','reject invalid number');
check(recibo_render('Oi {cliente}; {valor_pago}',array('cliente'=>'Exemplo','valor_pago'=>'100,00'))==='Oi Exemplo; 100,00','literal template placeholders');
check(recibo_outcome(array('error'=>0,'http'=>201,'body'=>array('key'=>array('id'=>'mock-id'))))===1,'only API acceptance with message ID is success');
check(recibo_outcome(array('error'=>28,'http'=>0,'body'=>null))===2,'timeout requires review, no blind retry');
check(recibo_outcome(array('error'=>0,'http'=>200,'body'=>array()))===2,'empty HTTP success requires review');
check(recibo_outcome(array('error'=>0,'http'=>401,'body'=>array()))===3,'rejected authorization is failure');
$s=recibo_defaults();$s['token']='mock-token';recibo_save($s);check(recibo_settings()['token']==='mock-token','settings persist outside public folder');
file_put_contents($tmp.'/test.log',str_repeat('old-line\n',10000)."\nnew-line\n");$tail=recibo_tail($tmp.'/test.log',1024);check(strlen($tail)<=1024&&strpos($tail,'new-line')!==false,'bounded log tail');
foreach(glob($tmp.'/*')as$f)unlink($f);rmdir($tmp);echo "No database or WhatsApp request executed.\n";
