<?php
require_once __DIR__.'/common.php';recibo_post();
file_put_contents(RECIBO_DATA.'/log_pagamentos.txt','',LOCK_EX);
header('Location: index.php',true,303);
