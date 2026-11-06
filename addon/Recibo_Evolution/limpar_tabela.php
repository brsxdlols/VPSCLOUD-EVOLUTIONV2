<?php
// Legacy cron compatibility: never delete pending receipts or financial data.
if(PHP_SAPI!=='cli'){require_once __DIR__.'/common.php';recibo_post();recibo_json(array('error'=>'Limpeza de pagamentos desativada. A rotacao trata apenas arquivos de log.'),410);}
