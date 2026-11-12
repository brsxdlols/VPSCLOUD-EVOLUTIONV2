# Operação, reconexão e rollback

## Antes de executar

Faça inventário em modo diagnose. Confirme o ambiente, número proprietário, portas, containers, mounts e serviços externos. O instalador não reconhece automaticamente toda topologia possível: em caso de dúvida interrompe. Separe janela e operador com acesso ao celular para qualquer novo pareamento.

Não confunda API HTTP 200, estado `open` e ack do servidor com mensagem legível. O aceite é no destinatário.

## Backup e atualização

`evolution-backup` atende somente ao layout padrão PostgreSQL local + Redis com persistência das instâncias. Aborta se o provider de autenticação for diferente. Mantém arquivos em `backups/session-DATA-PID`, modo protegido. Inspect e ENV contêm segredos: não publique esses arquivos.

Inclui dump PostgreSQL, catálogo, RDB, verificação estrutural Redis, imagem API, configuração e Manager. O arquivo `LATEST-SESSION-BACKUP` só é gravado ao concluir. A API volta a iniciar em caso de falha, mas verifique seu estado e a saúde antes de retomar tráfego.

Restaure PostgreSQL e Redis em serviços separados, sem rede externa e sem uma segunda API ligada ao WhatsApp. Verifique tabelas, contagens, hash de autenticação e `creds`, sem revelar valores. `pg_restore -l` e `redis-check-rdb` são verificações necessárias, mas não substituem esse ensaio de restauração. No servidor acompanhado, uma restauração isolada dos dois bancos foi executada com sucesso.

O upgrade automático cobre o layout padrão com API 2.3.4, PostgreSQL local e Redis local, após backup e ensaio das migrações em cópia numa rede interna sem acesso ao WhatsApp. A imagem 2.3.7 usa seu entrypoint original para migrar. Falha após a troca restaura os dois bancos antes de iniciar a API antiga; falha de recuperação mantém a API parada. Outros layouts/versões exigem revisão. Não execute dois containers API com a mesma identidade. Ao concluir a instalação sobre V2, os pareamentos são encerrados para novo QR; o histórico e as instâncias são mantidos. Restaurar backup não reativa credenciais revogadas no WhatsApp.

## Quando escolher reconexão

Na investigação acompanhada, reinício e atualização não resolveram a mensagem pendente. Novo pareamento permitiu envio legível de texto e boleto com outro número. Isso justifica testar renovação da sessão afetada com o operador disponível; não justifica fazer logout indiscriminadamente em toda instalação.

O reparo é deliberadamente separado do instalador:

```sh
EVOLUTION_CONFIRM_RECONNECT=MKAUTH evolution-reconnect MKAUTH
```

Ele faz backup, aguarda a API e chama DELETE `/instance/logout/MKAUTH`. Não chama `/instance/delete`, FLUSH, remoção de volumes ou SQL de exclusão. O logout usa o fluxo oficial da API e **pode remover credenciais e chaves da sessão**, como parte esperada de encerrar o vínculo. Preserve o backup e espere novo QR. Não prometa recuperação automática das mensagens antigas pendentes.

Depois, use o QR do Manager ou `evolution-qr-terminal MKAUTH`. O auxiliar consulta estado antes de solicitar conexão; uma sessão `open` não é desconectada por ele. QR contém credencial temporária: não compartilhe.

## Rollback

Para uma alteração somente de Manager, restaure sua pasta de backup e recarregue o navegador. Para troca de imagem sem alteração de esquema/estado, pare a nova API, preserve-a e recoloque o container/imagem e configuração anteriores. Verifique o entrypoint efetivo e o banco antes de iniciar.

Se houve migração de esquema/estado, a imagem antiga sobre o banco novo não é rollback comprovado. Restaure os backups em banco/volume separados e só troque os apontamentos depois de validar compatibilidade. Preserve os volumes originais. Alterações posteriores ao snapshot podem ser perdidas.

**Após logout, rollback de arquivos não reativa a autorização revogada pelo WhatsApp.** O operador precisará fazer novo pareamento. Essa limitação é apresentada antes da confirmação do reparo.

## Aceite

1. Confirmar número correto e instância `open`.
2. Enviar texto a dois destinatários controlados e confirmar legibilidade.
3. Enviar boleto/PDF e abrir o arquivo no destinatário.
4. Responder pelo destinatário e confirmar recepção pela API e Manager.
5. Validar a integração do sistema com destinatário controlado.
6. Em janela autorizada, reiniciar só a API e confirmar recuperação sem novo QR.

Ainda precisam de homologação integral: instalação do zero em host limpo, upgrade de cada versão suportada, rollback com migrações, boot do servidor e migração V1. Não anunciar o instalador como universal ou totalmente homologado com base nos testes unitários.
