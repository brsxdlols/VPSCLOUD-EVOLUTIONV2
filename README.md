# Evolution API 2.3.7 — instalador 7070 para MK-AUTH

O instalador oficial é `install-7070-replace-v1.sh`, com monitor no host, alertas Telegram e addon de recibos. Use o comando abaixo. O atalho antigo `patch-update-v237.sh` foi desativado; `install.sh` legado não faz parte deste fluxo.

**Estado:** instalação e atualização controladas. O fluxo padrão 2.3.4 → 2.3.7 cria backup, ensaia as migrações numa cópia sem acesso externo e valida a versão real da API. Uma V1 reconhecida é removida com backup privado antes de criar a V2. Em V2 existente, a execução encerra os pareamentos ao concluir e exige novo QR, preservando instâncias e histórico.

## Download e execução

Baixe o arquivo para revisá-lo antes de executar:

```sh
curl -fL --retry 3 https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/main/install-7070-replace-v1.sh -o /root/install-evolution-v2-7070.sh
EVOLUTION_MODE=diagnose sh /root/install-evolution-v2-7070.sh
# Depois de revisar o inventário e planejar a janela:
sh /root/install-evolution-v2-7070.sh
```

Para execução reproduzível, substitua o nome da branch pelo SHA do commit publicado. Dependências: root, Docker funcional, curl, OpenSSL, Python 3, cron, logrotate, utilitários POSIX e pelo menos espaço suficiente para imagens, dados e backups. O addon requer o layout MK-AUTH reconhecido, PHP 7.1+ com mysqli/curl/json e MariaDB com suporte a CREATE OR REPLACE TRIGGER. Outras versões interrompem a instalação do addon para revisão. A API é fixada pelo digest testado da imagem 2.3.7. PostgreSQL 15 e Redis 7.4 continuam usando tags; uma instalação nova resolve essas tags no momento do pull. Atualizar essas dependências não faz parte deste instalador.

## Comportamento

- Recuperação de rollback ativo: se `evolution_v2_api` está parado e existe um único `evolution_v2_api_rollback_*` ativo na mesma rede, porta 7070, bancos e volumes, salva os dois inspects em backup privado e recupera os nomes sem parar/reiniciar o serviço ativo. O container parado é preservado com reinício automático desabilitado. Diferenças ou múltiplos candidatos interrompem para revisão. Depois segue o upgrade normal, com backup completo e novo QR.

- Sem V2 e sem volumes V2 conhecidos: prepara PostgreSQL, Redis e Manager; cria uma única API com o entrypoint original, incluindo migrações.
- V2 com nomes e topologia esperados: preserva bancos e instâncias; pergunta a chave e mantém a atual com Enter; aplica PATCH do Manager, atualiza a API compatível e instala auxiliares. Ao concluir, desconecta os pareamentos para novo QR. O patch falha se o bundle não for reconhecido.
- API parada, backend ausente, volumes órfãos, rede diferente ou nome de container não padrão: interrompe para recuperação supervisionada.
- API 2.3.4 padrão: para a API, gera backup validado de PostgreSQL, Redis e imagem; testa 2.3.7 em rede interna com volumes separados antes da substituição. Em falha após substituir, restaura PostgreSQL e Redis antes de iniciar a API antiga. Se a restauração falhar, mantém a API parada e informa o backup para recuperação. Exige ao menos 4 GiB mais três vezes o tamanho dos dados livres; outras versões ou backends exigem revisão.

O monitor preserva o entrypoint/comando efetivo existente. O upgrade usa o entrypoint original da imagem nova para executar suas migrações. O novo QR é obrigatório em cada execução sobre V2 existente; apenas `EVOLUTION_FORCE_RECONNECT=0` desativa explicitamente essa política. O backup preserva dados, mas não reativa credenciais revogadas pelo logout no WhatsApp. A versão é verificada pela API e pela imagem; baixe novamente o instalador antes de executar.

Nomes suportados: `evolution_v2_api`, `evolution_v2_postgres`, `evolution_v2_redis`. Diretório padrão: `/opt/vpscloud-evolution-v2`. A porta externa é 7070 (`EVOLUTION_PORT` em instalação nova). Para NAT use `EVOLUTION_SERVER_URL=http://ENDERECO_EXTERNO:PORTA`. O instalador não cria encaminhamento no roteador nem muda o MK-AUTH.

O instalador pergunta a API Key Global com texto visível ao digitar. Em instalação nova, Enter gera uma chave aleatória; em instalação existente, Enter mantém a chave atual. A seleção é mostrada no terminal interativo e armazenada no ENV protegido. Use de 6 a 128 letras, números, ponto, hífen ou sublinhado. Para automação sem terminal, `EVOLUTION_API_KEY` define a escolha; sem essa variável, a chave existente é mantida ou uma nova é gerada.

Quando você escolhe outra chave para uma V2 existente, somente a API é recriada com a mesma imagem, rede, portas e mounts. O estado anterior é preservado em backup e retomado se a verificação de saúde/autenticação falhar. O monitor usa a chave efetiva do container. O token do addon local é atualizado apenas quando coincide com a antiga chave global e aponta para a mesma API. Tokens de instância ou integrações externas não são substituídos: se usavam a chave global antiga, atualize-os após a troca.

## Manager e manutenção

### Acesso pelo addon do MK-AUTH

O instalador inclui `/admin/addons/evolution/`, com abas **Manager** e **Alertas Telegram**, e atalhos no menu Provedor. O Apache faz proxy somente para a porta local da Evolution, incluindo WebSocket; basta o acesso web habitual do MK-AUTH, sem publicar outra porta. O login nativo emite um ticket HttpOnly de curta duracao, renovado enquanto a sessao estiver valida. Manager e monitor continuam pedindo a API Key Global. O segredo do proxy fica fora da pasta publica e nao e a chave da API.

Requer Apache2 com proxy, proxy_http e proxy_wstunnel. HTTP e WebSocket usam caminhos internos separados no mesmo dominio. A configuracao e validada antes do reload; em erro, a configuracao anterior e restaurada. Nginx ou outros servidores exigem configurar o proxy equivalente, e o instalador informa essa limitacao. O monitor precisa estar habilitado. `EVOLUTION_INSTALL_WEB_ADDON=0` pula a instalacao/atualizacao dessa integracao. O comando `evolution-install-web-addon` reaplica apenas o addon/proxy quando os auxiliares novos ja estiverem carregados.

Na tela **Opcoes → WhatsApp → Servidor**, um endereco vazio recebe o IP IPv4 de saida da maquina e a porta publicada da API, por exemplo `172.16.30.25:7070`, e seleciona Evolution2 API. Instancia e chave nao sao alteradas. O botao **Configurar servidor WhatsApp** do addon permite preencher esse endereco tambem quando ja existe outro: revise instancia/chave e clique em Gravar no MK-AUTH. O preenchimento da pagina nao grava o banco automaticamente.

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

Os arquivos legados `install.sh` e `patch-update-v237.sh` não compõem este fluxo revisado; não execute esses atalhos como alternativa. As versões são promovidas para `main` após os testes da branch de correção.


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


## Substituição automática da V1

O instalador identifica o container padrão `evolution_api` com imagem V1 reconhecida (`atendai`, `evolutionapi` ou `evoapicloud/evolution-api:v1.x`). Tags `latest` dessas imagens só são aceitas após ler o package.json do container e comprovar versão 1.x. Baixa as imagens V2 antes de parar a V1. Salva inspect, imagem, filesystem e mounts, valida os arquivos e checksums e só então remove o container, volumes exclusivos, diretórios V1 identificados, redes exclusivas sem uso e imagem não compartilhada. Backups ficam em `/root/evolution-v1-backups/before-v2-*`, restritos a root. Não são apagados.

Pastas reconhecidas: `/opt/evolution`, `/opt/evolution-api`, `/opt/vpscloud-evolution`, somente quando identificadas pelos mounts ou pelo projeto Compose da V1. Pastas de outros serviços, mounts compartilhados e volumes V2 não são excluídos. Nomes/imagens desconhecidos ou recursos compartilhados bloqueiam a remoção para não atingir outra aplicação. Em caso de falha de backup, a V1 que estava ligada é reiniciada. Depois da exclusão, falhas na instalação V2 exigem recuperação a partir do backup; não há rollback automático de dados.

A V2 usa bancos novos; configure o MK-AUTH para a nova URL/instância/chave e conecte o WhatsApp por novo QR. Esta operação descarta o uso das sessões antigas e não transfere automaticamente dados ou histórico da V1. O helper `evolution-retire-v1.py --plan` oferece inventário sem parar/excluir a V1. O instalador em `EVOLUTION_MODE=diagnose` continua somente leitura.

Instalações novas do addon começam desativadas. Há um único switch destacado no topo para os envios; ele substitui a antiga combinação de controle principal e checkbox de automático. Em atualizações, o estado efetivo anterior é preservado (qualquer bloqueio anterior continua desligado). O teste fictício e a consulta retroativa permanecem.

O auxiliar do monitor preserva explicitamente Entrypoint, Cmd e diretório de trabalho da API existente, além da imagem por ID, portas e mounts. Assim, instalações antigas com início direto por Node ou wrapper de shell podem receber o monitor sem trocar o comando de execução ou a versão da API.
