# Sistema de Vouchers Wi-Fi

Sistema completo para emissão automatizada de vouchers de acesso Wi-Fi via totem com leitor de cartão RFID, com painel administrativo para gestão de estoque, consulta de credenciais e emissão manual.

Desenvolvido para operar 100% em rede local, integrando três sistemas externos (controlador de rede, sistema de credenciais e sistema de autenticação corporativa) em um fluxo único e auditável.

## Visão geral

O projeto resolve um problema operacional real: liberar acesso à internet para visitantes/usuários de forma rápida, segura e sem depender de um atendente humano em cada emissão, mantendo controle de estoque de vouchers e histórico completo de quem recebeu o quê.

Há dois fluxos de uso, com modelos de acesso independentes:

- **Totem (kiosk)** — um leitor RFID emula um teclado; ao aproximar o cartão, o sistema identifica o usuário no sistema de credenciais, valida o tipo de usuário permitido e libera automaticamente um voucher de Wi-Fi já pronto em estoque, imprimindo uma etiqueta com os dados de acesso. Sem login — protegido por chave de API dedicada ao totem.
- **Gerência (admin)** — painel web com login real (autenticado contra o sistema corporativo da empresa), usado pela coordenação para consultar pessoas, gerar/substituir/cancelar vouchers manualmente e acompanhar estoque e histórico de emissões.

## Principais funcionalidades

- Emissão de voucher por leitura de cartão RFID, sem intervenção manual
- Validação de usuário por tipo/perfil antes da liberação
- Reposição automática diária de estoque de vouchers (geração em lote no controlador de rede)
- Limpeza automática diária de vouchers expirados, liberando o cartão/credencial para nova emissão
- Impressão de etiqueta em impressora de rede (protocolo EPL)
- Painel administrativo com login corporativo real (sem senha própria do sistema)
- Consulta de pessoas/credenciais, geração e cancelamento manual de vouchers
- Histórico completo de emissões e visão de estoque em tempo real

## Arquitetura

```
┌─────────────┐        ┌──────────────┐        ┌──────────────────────┐
│  Totem RFID │        │   Painel     │        │                       │
│  (kiosk)    │        │   Gerência   │        │   Integrações         │
└──────┬──────┘        └──────┬───────┘        │   externas            │
       │                      │                 │                       │
       │   React (Vite SPA)   │                 │  • Omada Controller   │
       └──────────┬───────────┘                 │    (vouchers Wi-Fi)   │
                   │ HTTP                        │  • iControl          │
            ┌──────▼───────┐                     │    (credenciais RFID)│
            │  Nginx        │                     │  • Sistema corp.     │
            │  (proxy +     │                     │    (login de admin)  │
            │  build da SPA)│                     └───────────▲───────────┘
            └──────┬───────┘                                 │
                   │                                          │
            ┌──────▼───────┐        ┌──────────┐              │
            │  Flask API    │───────▶│  MySQL   │              │
            │  (Gunicorn)   │        │          │              │
            └──────┬───────┘        └──────────┘              │
                   │                                          │
            ┌──────▼───────┐                                  │
            │  Scheduler    │──────────────────────────────────┘
            │  (cron diário)│
            └───────────────┘
```

Toda a comunicação entre frontend e backend acontece via HTTP puro (sem SSR, sem build compartilhado), o que permite escalar, testar e substituir cada camada de forma independente.

### Stack

| Camada       | Tecnologia                              |
|--------------|------------------------------------------|
| Frontend     | React 19 + TypeScript + Vite             |
| Backend      | Python + Flask + Gunicorn                |
| Banco        | MySQL 8                                  |
| Proxy/Web    | Nginx                                    |
| Orquestração | Docker Compose (4 containers)            |
| Automação    | Cron (container dedicado)                |

### Containers

O sistema roda como quatro containers Docker orquestrados por `docker-compose.yml`:

| Container   | Responsabilidade                                                        |
|-------------|---------------------------------------------------------------------------|
| `mysql`     | Banco de dados, schema criado automaticamente na primeira execução        |
| `flask`     | API REST (voucher, estoque, autenticação, consulta de credenciais)        |
| `nginx`     | Serve o build da SPA e faz proxy reverso das rotas de API                 |
| `scheduler` | Cron diário para reposição de estoque e limpeza de vouchers expirados     |

### Integrações externas

- **TP-Link Omada Controller** — geração, consulta e cancelamento de vouchers de Wi-Fi
- **iControl** — busca de credenciais/cartões RFID por número, nome ou identificador
- **Sistema corporativo (Vitae/NTI)** — validação real de login da equipe de gerência, sem senha própria armazenada

### Automação diária

Um container de cron dedicado dispara duas rotinas via HTTP contra a própria API, reaproveitando a mesma lógica exposta ao totem:

- **Reposição de estoque** — quando o estoque disponível atinge o limite mínimo, gera e insere novos vouchers automaticamente até o limite máximo configurado
- **Limpeza de expirados** — verifica vouchers emitidos que não são mais válidos no controlador e libera o registro correspondente

## Segurança

- Painel de gerência protegido por login real contra sistema corporativo, com sessão em banco (compatível com múltiplos processos do servidor)
- Endpoints do totem protegidos por chave de API dedicada
- Usuário de banco de dados dedicado à aplicação, com privilégios restritos ao próprio schema (sem acesso administrativo)
- Rede local isolada, sem exposição externa
- Rotação de logs configurada em todos os containers para evitar consumo indevido de disco

## Como executar

O ambiente completo sobe via Docker Compose — veja instruções detalhadas em [`CLAUDE.md`](./CLAUDE.md).

```powershell
cd vouchers
copy .env.example .env      # preencher credenciais reais
docker compose up -d --build
```

Isso inicia banco de dados, API, frontend (servido pelo Nginx) e o container de automação diária.

## Estrutura do repositório

```
vouchers/         API Flask, integrações externas, schema e lógica de estoque
frontend/         SPA React/Vite (totem + painel de gerência)
deploy/           Configuração de Nginx, MySQL e scheduler para produção
banco de dados/   Referência histórica do schema
projetoTeste/     Protótipo inicial (não faz parte do sistema em produção)
```

## Status

Em produção, rodando de forma contínua em ambiente Docker sobre Debian, atendendo emissão de voucher via totem e gestão via painel administrativo.
