<?php
require_once __DIR__.'/common.php';
if (PHP_SAPI!=='cli') recibo_post();
try {
    $db=recibo_db();$out=recibo_run($db,PHP_SAPI!=='cli',1);$db->close();
    if (PHP_SAPI!=='cli') recibo_json($out);
} catch (Exception $e) {
    recibo_log(0,'WORKER_ERROR');
    if (PHP_SAPI!=='cli') recibo_json(array('error'=>$e->getMessage()),500);
    exit(1);
}
