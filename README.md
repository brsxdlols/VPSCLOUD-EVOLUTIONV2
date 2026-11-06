# Evolution API 2.3.7 — instalador 7070 para MK-AUTH

Esta branch contém o instalador revisado `install-7070-replace-v1.sh`, auxiliares de backup e novo pareamento, e correções do Manager. Não utilize os comandos antigos da `main` para instalar esta revisão.

**Estado:** revisão para instalação controlada e PATCH. Atualização automática de uma imagem diferente permanece bloqueada. Migração V1 → V2 não é automática. Os testes de proteção não substituem homologação completa de instalação, atualização e rollback.

## Download e execução

Baixe o arquivo para revisá-lo antes de executar:

```sh
curl -fL --retry 3 https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/install-7070-replace-v1.sh -o /root/install-evolution-v2-7070.sh
EVOLUTION_MODE=diagnose sh /root/install-evolution-v2-7070.sh
# Depois de revisar o inventário e planejar a janela:
sh /root/install-evolution-v2-7070.sh
```

Para execução reproduzível, substitua o nome da branch pelo SHA do commit publicado. Dependências: root, Docker funcional, curl, OpenSSL, utilitários POSIX e pelo menos espaço suficiente para imagens, dados e backups. A API é fixada pelo digest testado da imagem 2.3.7. PostgreSQL 15 e Redis 7.4 continuam usando tags; uma instalação nova resolve essas tags no momento do pull. Atualizar essas dependências não faz parte deste instalador.

## Comportamento

- Sem V2, sem V1 e sem volumes conhecidos: prepara PostgreSQL, Redis e Manager; cria uma única API com o entrypoint original, incluindo migrações.
- V2 com nomes e topologia esperados: preserva ENV, chave de API, bancos e sessão; aplica PATCH do Manager e instala auxiliares. O patch usa correspondência explícita de código e falha se o bundle não for reconhecido.
- API parada, backend ausente, volumes órfãos, rede diferente, V1 ou nome de container não padrão: interrompe para recuperação supervisionada.
- Imagem diferente: pode preparar dump e baixar a imagem, mas não substitui o container. O dump preparatório não é backup completo da autenticação.

Nomes suportados: `evolution_v2_api`, `evolution_v2_postgres`, `evolution_v2_redis`. Diretório padrão: `/opt/vpscloud-evolution-v2`. A porta externa é 7070 (`EVOLUTION_PORT` em instalação nova). Para NAT use `EVOLUTION_SERVER_URL=http://ENDERECO_EXTERNO:PORTA`. O instalador não cria encaminhamento no roteador nem muda o MK-AUTH.

Instalações novas recebem chave global aleatória, armazenada em `evolution-v2.env` protegido. Não é impressa no terminal. Instalações existentes preservam a chave; nenhuma rotação silenciosa é feita.

## Manager e manutenção

Preserva logo VPSCloud, normalização brasileira, telefone opcional, fallback de clipboard em HTTP e backup do Manager. O botão Chat/+ agora abre conversa para número informado. Recarregue com Ctrl+F5 depois do PATCH. Esse botão foi validado no ambiente acompanhado; o comportamento visual de contatos novos ainda deve ser homologado em outros bundles.

Não há limpeza global automática por padrão. `EVOLUTION_INSTALL_CLEANUP=1` instala somente relatório de armazenamento; não apaga mensagens, imagens Docker, backups, caches ou logs do MK-AUTH. Crons antigos não são removidos silenciosamente: revise-os antes de continuar. Os logs próprios do Recibo Evolution agora usam a política unificada de até sete dias. Logs de containers novos usam os limites do driver Docker.

## Backup, QR e reconexão assistida

## Inicialização e alertas Telegram

API, PostgreSQL e Redis novos usam `--restart=always`; o PATCH também atualiza essa política nos três containers atuais, sem reiniciá-los. A política antiga `on-failure` da API não garantia retorno depois do reinício do daemon. A política não substitui a habilitação do serviço Docker no init do host.

Depois de instalar os auxiliares, execute, em janela de manutenção:

```sh
evolution-install-monitor
```

Esse auxiliar requer Python 3, habilita Docker e cron em SysV/Devuan ou systemd e instala a página `/monitor/` no mesmo acesso da API. Na primeira execução há uma breve parada da API para adicionar um mount e carregar o módulo do painel. O container anterior é preservado com reinício desativado; imagem, ambiente, portas e mounts existentes são preservados no layout suportado. Topologias diferentes são recusadas.

Entre na página com a chave global da API. Configure token e chat Telegram para Docker/API, escolha as instâncias monitoradas e, se necessário, destinos diferentes para cada uma. Salve e use os botões de teste. Tokens não são retornados pela API e ficam em arquivo de configuração protegido; a chave de login permanece somente na memória da página. Utilize o acesso HTTPS do seu ambiente para transmitir credenciais.

O cron verifica a cada minuto, avisa após duas falhas consecutivas e repete a cada 30 minutos. A recuperação envia um aviso. Alertas por instância incluem o número WhatsApp identificado pela API; quando desconectada, o número é indicado como último identificado e fica disponível mesmo com Docker parado. Pode iniciar Docker ausente e os três containers parados; não reinicia um daemon vivo travado, não recria containers e não renova sessões. Alertas precisam de servidor, cron, rede e Telegram funcionando; desligamento total do host exige monitor externo.

Para manutenção planejada: `touch /run/vpscloud-evolution-maintenance`; ao concluir, `rm /run/vpscloud-evolution-maintenance`. Backups e o instalador usam locks que também pausam o watchdog. Estado local: `python3 /opt/vpscloud-evolution-v2/monitor/evolution-watchdog.py --status`.

## Backup, QR e reconexão assistida

```sh
evolution-backup
evolution-qr-terminal MKAUTH
# Somente se o reparo foi escolhido e o celular correto está disponível:
EVOLUTION_CONFIRM_RECONNECT=MKAUTH evolution-reconnect MKAUTH
```

O backup interrompe brevemente somente a API, gera PostgreSQL e Redis coordenados, preserva configuração, Manager e imagem, e reinicia a API. Verifica catálogo e estrutura RDB. Exige backend Redis padrão. Teste a restauração isolada antes de qualquer atualização. Não execute junto com outro operador alterando a instalação ou com produtores externos escrevendo diretamente nos backends.

A reconexão faz esse backup e depois solicita **logout da sessão escolhida**, sem excluir a instância Evolution. É necessário escanear novo QR. Logout revoga o vínculo no WhatsApp: restaurar o backup não reativa credenciais revogadas. Confira o número remetente antes de liberar automações.

## Validação e limites

No ambiente acompanhado, texto e boleto PDF enviados pelo sistema chegaram legíveis após novo pareamento com outro número na instância original. Isso associa a falha à sessão/conta anterior, mas não identifica o defeito criptográfico exato e não comprova que todo número foi recuperado. Não há reset automático de sessões no instalador.

```sh
node tests/installer.test.cjs
```

Testes cobrem sintaxe POSIX, diagnóstico sem mutação, V1, volumes órfãos, nomes distintos, API parada, ENV ausente, rede distinta, estado parcial, confirmação do reparo e patch do Manager. Não executam instalação real nem enviam WhatsApp. Leia [operação e recuperação](docs/OPERACAO-SEGURA.md).

Os arquivos legados `install.sh` e `patch-update-v237.sh` não compõem este fluxo revisado; não execute esses atalhos como alternativa. Nenhuma alteração foi publicada diretamente na `main` por esta revisão.


### Imagens dos alertas

O monitor envia cartões PNG junto da legenda com servidor, instância, número e motivo: vermelho para Docker/API indisponível, amarelo para WhatsApp desconectado e verde para recuperação. As imagens ficam no host e não dependem da API Docker para serem enviadas. Se o envio da foto falhar ou o arquivo não estiver disponível, o monitor tenta entregar o aviso em texto.

Arquivos: [crítico](assets/alerts/critical.png), [WhatsApp](assets/alerts/whatsapp.png) e [recuperação](assets/alerts/recovery.png). O botão de teste do painel continua sendo uma mensagem de texto; as imagens são aplicadas aos eventos automáticos.


### Ajuda de configuração do Telegram

Após o login no `/monitor`, o botão **Como criar um bot e grupo** abre o passo a passo de BotFather, criação do grupo, inclusão do bot, obtenção do Chat ID e configuração dos destinos. Os botões **Salvar e testar** gravam os campos preenchidos antes de enviar o teste; se a gravação falhar, o teste não é enviado. O resultado aparece em um aviso fixo na tela.


## Recibos e limites de logs

O instalador inclui o monitor no host e o addon Recibo Evolution quando detecta MK-AUTH. Para instalação gerenciada externamente, use `EVOLUTION_INSTALL_MONITOR=0` ou `EVOLUTION_INSTALL_RECIBO=0`. Os auxiliares também ficam disponíveis como `evolution-install-monitor` e `evolution-install-recibo`. Backups são privados e preservados.

No MK-AUTH, abra **Recibos via WhatsApp** no menu ou `/admin/addons/Recibo_Evolution/`. O botão **Editar template da mensagem** permite alterar o recibo e visualizar um exemplo sem envio. Instalação nova mantém o envio automático desligado; revise provedor, instância e template antes de ativar. Não há reenvio automático de resultados incertos. Veja [detalhes do addon](addon/README.md).

Logs próprios do monitor/limpeza/recibos usam até sete rotações, `maxage 7`, compressão e verificação de tamanho a cada cinco minutos (5 MiB por arquivo; daemon Docker 10 MiB). Esse prazo aplica-se às rotações; o arquivo ativo permanece e é limitado por tamanho. Logs dos três contêineres padrão continuam sob Docker, até três arquivos de 10 MiB por contêiner. Não são apagados sessões, mensagens, filas ou backups. Outros logs do MK-AUTH e crescimento do banco precisam de gestão própria. O monitor alerta a partir de 80% de uso de disco; 90% ou menos de 1 GiB livre é crítico. Alertas dependem do host e da rede estarem funcionando.

O atalho **Recibos via WhatsApp** fica nos menus **Financeiro** e **Provedor**. No addon, **Usar servidor WhatsApp do MK-AUTH** importa a conexão nativa sem exibir o token; **Descartar recibos pendentes sem enviar** esvazia a fila pendente atual mantendo o histórico e os pagamentos. O descarte não altera registros já enviados, em revisão ou com falha.

O controle principal de comprovantes fica no topo do addon e bloqueia envios automáticos/manuais/retroativos sem apagar configuração. A retomada normal processa só pagamentos de hoje, um por execução; anteriores ficam descartados sem envio. Exceção de fim de semana: consultar 1–3 dias anteriores e confirmar um registro individual, nunca um lote.
