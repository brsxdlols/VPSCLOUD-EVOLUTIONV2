# VPSCLOUD Evolution API v2 para MK-Auth

Instalador da Evolution API `v2.3.4` para servidores MK-Auth antigos que já
possuem Docker, inclusive Docker `18.09`.

O projeto instala:

- Evolution API `v2.3.4`;
- PostgreSQL 15;
- Redis 7.4;
- volumes persistentes para banco e cache;
- Evolution Manager na porta `3100`;
- logo local, sem depender do endereço externo removido;
- backup da Evolution v1 antes da instalação;
- parada automática do contêiner v1 após a v2 responder HTTP `200`.

## Instalação

Execute como `root`:

```bash
curl -fsSL https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/main/install.sh -o /root/install-evolution-v2.sh
chmod +x /root/install-evolution-v2.sh
sh /root/install-evolution-v2.sh
```

Ao terminar:

```text
Manager: http://IP_DO_SERVIDOR:3100/manager
Global API Key: 123456
```

Se o servidor estiver atrás de NAT, informe o endereço público:

```bash
EVOLUTION_SERVER_URL=http://IP_PUBLICO:3100 sh /root/install-evolution-v2.sh
```

## Migração da v1

O instalador faz backup da Evolution v1 e, depois que a API v2 responde HTTP
`200`, executa:

```bash
docker stop evolution_api
```

O contêiner e a imagem da v1 não são apagados. Após a instalação:

1. abra o Manager da v2;
2. crie a instância desejada;
3. conecte o WhatsApp pelo QR Code;
4. altere no MK-Auth o servidor para a porta `3100`;
5. faça um envio controlado.

Os backups da v1 são salvos em:

```text
/root/evolution-v1-backups/
```

Para um rollback imediato:

```bash
docker start evolution_api
```

## Contêineres e volumes

```text
evolution_v2_api
evolution_v2_postgres
evolution_v2_redis

evolution_v2_postgres_data
evolution_v2_redis_data
```

## Observação de segurança

A chave global `123456` foi definida como padrão operacional solicitado.
Recomenda-se restringir a porta `3100` por firewall a endereços confiáveis.

## Licença

Este instalador é distribuído sob a licença MIT. A Evolution API possui sua
própria licença e permanece propriedade de seus respectivos autores.
