# Recibo Evolution — integração MK-AUTH

Implementação VPSCloud compatível com PHP 7.1 e o layout do addon Recibo Evolution API 7.5, de Valteir. O addon anterior é preservado em backup privado; seu código, credenciais e dados de clientes não são publicados neste pacote.

O setup CLI cria apenas a fila do addon, metadados de envio, usuário MariaDB dedicado e trigger de captura de transição para `pago`. Não altera valores, vencimentos ou situação de títulos. A página não executa DDL. A captura usa `INSERT IGNORE` para impedir que atualizações repetidas de um título já pago derrubem a transação por chave duplicada.

Envio automático começa desativado em instalação nova. Configure a instância/número correto, edite o template, faça uma prévia sem envio e só depois ative. O processo aceita apenas um recibo por acionamento manual, bloqueia concorrência e limita tempo/lote no cron. Respeita `zap` e `cli_ativado` do cliente. Nunca tenta o payload v1 antes do v2.

Estados da fila: `0` pendente, `1` aceito pela API, `2` revisão necessária, `3` falha ou contato ignorado. Uma chamada incerta permanece em revisão; uma queda depois do aceite pode impedir saber se houve entrega. Não existe garantia de exactly-once entre HTTP e MariaDB. O operador deve conferir antes de recolocar um recibo, pois isso pode duplicá-lo.

O template tem campos `{cliente}`, `{cpf_cnpj}`, `{id_pagamento}`, `{data_pagamento}`, `{data_vencimento}`, `{valor}`, `{valor_pago}`, `{coletor}`, `{forma_pagamento}` e `{provedor}`. A prévia usa dados fictícios. Token vazio preserva o atual; nenhuma resposta da API ou corpo de mensagem é gravado no log. A tela carrega só 100 registros e até 64 KiB de log.

Dados privados ficam em `/opt/mk-auth/dados/Recibo_Evolution`, fora da pasta pública. O acesso web exige sessão administrativa MK-AUTH e CSRF para alterações. O cron é gerido pelo instalador, não pelo usuário web. Logs são rotacionados por tamanho e até 7 dias. Pagamentos pendentes e histórico da fila não são apagados automaticamente.

Rollback: pause o cron específico, preserve a nova fila, restaure os arquivos e `addon.js` do backup e a definição anterior do trigger registrada em `trigger-before.json`. Se não havia trigger, remova somente `tig_brl_pag` criado pelo addon. Não restaure uma tabela financeira inteira nem altere `sis_lanc`/`sis_cliente`. Não exclua filas ou registros para desfazer uma atualização. Antes de voltar ao worker antigo, avalie os estados novos `2/3` e mantenha envio automático parado para evitar repetição.

O botão **Descartar recibos pendentes sem enviar** marca somente `envio=0` como `4` sob o mesmo lock do worker. Preserva o histórico e os pagamentos, não marca como entregue e não altera registros em revisão. Exige sessão MK-AUTH, CSRF e confirmação. Novos pagamentos continuam capturados.

O botão **Usar servidor WhatsApp do MK-AUTH** importa e salva a conexão atual de Opções → WhatsApp → Servidor (Evolution2 API), preservando template e agendamento. A leitura usa uma view restrita às quatro opções do gateway; não concede acesso às demais senhas de `sis_opcao`. O token não é devolvido ao navegador. O acesso dos botões usa o mesmo bootstrap de sessão nativa da página.

Simulações de próximo recibo e descarte só leem a fila e não chamam a Evolution API. O descarte oferece todos os pendentes ou apenas anteriores a hoje, considerando `datapag` e `CURDATE()` do banco; datas ausentes são tratadas como antigas. A simulação é uma fotografia: o automático continua ativo se estiver habilitado. Para testes com fila parada, desative e salve o agendamento primeiro.

O teste real usa conexão/template salvos, dados fictícios e exclusivamente o número informado e confirmado, sem consumir a fila. Exige CSRF, instância conectada e espera de 60 segundos entre testes na mesma sessão. Resultado incerto não é reenviado automaticamente. O teste de regressão HTTP usa uma API falsa em loopback; não envia mensagens WhatsApp.

O controle principal de envios fica no topo: desligado bloqueia comprovantes automáticos, manuais e retroativos, preservando configurações. Um envio já iniciado pode concluir. Testes fictícios e simulações continuam disponíveis. Ele é independente do agendamento automático.

A retomada normal aceita somente pagamentos do dia atual no banco. Ao voltar a uma instância conectada, pendentes anteriores/sem data são marcados como descartados sem envio, e apenas um recibo do dia é processado por execução, respeitando o intervalo automático configurado. A consulta retroativa é manual, de 1 a 3 dias anteriores, limitada a 100 opções e a um registro por confirmação. Ela inclui somente pendentes/descartados, excluindo já aceitos, falhas e revisões. Não existe envio retroativo em lote. O operador deve verificar recebimentos por outros canais antes de confirmar.
