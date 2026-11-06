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
