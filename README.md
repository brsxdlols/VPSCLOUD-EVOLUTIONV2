# VPSCLOUD Evolution API v2 para MK-Auth

Instaladores da Evolution API `v2.3.4` para servidores MK-Auth antigos que já possuem Docker, inclusive Docker `18.09`.

O projeto instala Evolution API v2.3.4, PostgreSQL 15, Redis 7.4, volumes persistentes, Manager com logo local e as correções de telefone opcional e cópia de token por HTTP. A Global API Key padrão é `123456`.

## Escolha do instalador

Existem dois modos independentes. Escolha somente um deles.

### 1. Instalação paralela na porta 3100

Mantém o contêiner e a imagem da Evolution v1 para rollback. Depois que a v2 responder HTTP `200`, o instalador apenas para o contêiner v1.

```bash
curl -fsSL https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/main/install.sh -o /root/install-evolution-v2.sh
chmod +x /root/install-evolution-v2.sh
sh /root/install-evolution-v2.sh
```

Acesso: `http://IP_DO_SERVIDOR:3100/manager`. Nesse modo é necessário alterar no MK-Auth a porta da Evolution para `3100`. Para reativar a v1: `docker start evolution_api`.

### 2. Substituição total da v1 na porta 7070

Use este modo para manter o mesmo IP e a mesma porta já configurados no MK-Auth. O instalador cria o backup, prepara PostgreSQL e Redis, para e remove o contêiner `evolution_api` da v1 e seus volumes anônimos, tenta remover a imagem antiga e sobe a v2 na porta `7070`.

```bash
curl -fsSL https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/main/install-7070-replace-v1.sh -o /root/install-evolution-v2-7070.sh
chmod +x /root/install-evolution-v2-7070.sh
sh /root/install-evolution-v2-7070.sh
```

Acesso: `http://IP_DO_SERVIDOR:7070/manager`. Nesse modo não é necessário alterar a porta usada pelo MK-Auth. A v1 é removida e não pode ser recuperada com `docker start`; o backup permanece disponível para reinstalação manual.

## Backup da Evolution v1

Nos dois modos, os backups são salvos antes da substituição em:

```text
/root/evolution-v1-backups/
```

O caminho do backup mais recente fica em `/root/evolution-v1-backups/LAST_BACKUP`.

## Telefone na criação da instância

O campo é opcional. Quando preenchido, aceita DDD + número com 8 ou 9 dígitos. O Manager remove espaços, parênteses e hífens e acrescenta `55` para números brasileiros de 10 ou 11 dígitos. Ele não adiciona nem remove o nono dígito. O botão de copiar token possui fallback para HTTP.

## Servidor atrás de NAT

Porta 3100:

```bash
EVOLUTION_SERVER_URL=http://IP_PUBLICO:3100 sh /root/install-evolution-v2.sh
```

Substituição total na porta 7070:

```bash
EVOLUTION_SERVER_URL=http://IP_PUBLICO:7070 sh /root/install-evolution-v2-7070.sh
```

## Contêineres e volumes da v2

```text
evolution_v2_api
evolution_v2_postgres
evolution_v2_redis

evolution_v2_postgres_data
evolution_v2_redis_data
```

## Limpeza automática de armazenamento

Os dois instaladores configuram uma manutenção diária às `03:25`. Por padrão,
ela mantém 7 dias de mensagens no PostgreSQL, limita o crescimento dos logs,
remove recursos Docker não utilizados há 7 dias, limpa o cache do APT e mantém
somente os dois backups mais recentes da Evolution v1.

Os volumes Docker ativos, as instâncias e as configurações não são apagados. A
retenção pode ser alterada durante a instalação:

```bash
EVOLUTION_RETENTION_DAYS=15 sh /root/install-evolution-v2.sh
```

O cron e o relatório ficam em:

```text
/etc/cron.d/vpscloud-evolution-cleanup
/var/log/vpscloud-evolution-cleanup.log
```
## Observação de segurança

A chave global `123456` foi definida como padrão operacional solicitado. Recomenda-se restringir a porta escolhida por firewall a endereços confiáveis.

## Licença

Este instalador é distribuído sob a licença MIT. A Evolution API possui sua própria licença e permanece propriedade de seus respectivos autores.
