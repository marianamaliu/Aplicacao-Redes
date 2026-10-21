*README EXPLICANDO COMO RODAR O PROJETO(O OUTRO EQUIVALE AO RELATORIO)*

# Trabalho de Redes — Checkpoint 2

Aplicação cliente-servidor desenvolvida em Python utilizando sockets TCP.

Nesta entrega, cliente e servidor realizam o handshake de três vias e depois
funcionam como um chat: os dois podem enviar mensagens a qualquer momento,
considerando um canal sem erros e perdas. O servidor continua aguardando novos
clientes depois que um se desconecta. O protocolo completo (checksum, janela,
Go-Back-N, Repetição Seletiva, timeout e encerramento) está descrito no
`relatorio2.md`.

## Requisitos

- Python 3 instalado
- Dois terminais abertos na pasta do projeto

Não é necessário instalar nenhuma biblioteca externa. O projeto utiliza apenas
módulos da biblioteca padrão do Python (`socket`, `json`, `threading`, `queue`,
`secrets`, `time` e `zlib`).

## Arquivos principais

- `servidor.py` — aguarda conexões, valida o handshake e conversa com o cliente.
- `cliente.py` — pede os parâmetros ao usuário, realiza o handshake e conversa
  com o servidor.
- `protocolo.py` — código comum aos dois lados: formato dos pacotes, checksum,
  envio com GBN/SR, recebimento, ACKs e encerramento. Não é executado sozinho.
- `padrao_msgs.txt` — padrão das mensagens exibidas no terminal.
- `relatorio2.md` — relatório do checkpoint 2.

## Como executar

### 1. Primeiro terminal — Servidor

```bash
python servidor.py
```

Deverá aparecer:

```text
server aguardando conexão em 0.0.0.0:2000 (Ctrl+C para encerrar)
```

**Mantenha esse terminal aberto.** Para encerrar o servidor, pressione Ctrl+C.

### 2. Segundo terminal — Cliente

```bash
python cliente.py
```

O cliente pede os parâmetros da conexão:

```text
Configuração da conexão
Modo de operação (individual/lote): lote
Protocolo (GBN/SR): GBN
Tamanho máximo do texto: 100
```

### 3. Conversando

Depois do handshake, os dois terminais mostram:

```text
[CLIENTE] Digite a mensagem (ou 'sair' para encerrar):
```

```text
[SERVIDOR] Digite a mensagem (ou 'sair' para encerrar):
```

Em qualquer um dos dois, digite a mensagem, tecle Enter e informe o tamanho de
cada pacote:

```text
olá mundo, tudo bem?
[CLIENTE] Modo: em lote
[CLIENTE] Tamanho de cada pacote (1 a 4 caracteres):
4
```

O lado que enviou mostra os pacotes saindo e a confirmação:

```text
[CLIENTE] Enviando pacote seq=293991314 payload="olá "
[CLIENTE] Enviando pacote seq=293991315 payload="mund"
[CLIENTE] Enviando pacote seq=293991316 payload="o, t"
[CLIENTE] Enviando pacote seq=293991317 payload="udo "
[CLIENTE] Enviando pacote seq=293991318 payload="bem?"
[CLIENTE] ACK recebido: ack=293991314
[CLIENTE] ACK recebido: ack=293991315
[CLIENTE] ACK recebido: ack=293991316
[CLIENTE] ACK recebido: ack=293991317
[CLIENTE] ACK recebido: ack=293991318
[SUCCESS] Lote enviado corretamente (ACK) time=1ms
```

No modo `lote`, os pacotes são enviados em lotes de até 5 (o tamanho da janela).
O lote seguinte só é enviado depois que todos os pacotes do lote atual forem
confirmados, e cada lote termina com o seu próprio `[SUCCESS]`. Uma mensagem
maior aparece assim:

```text
[CLIENTE] Enviando pacote seq=1768004229 payload="uma "
[CLIENTE] Enviando pacote seq=1768004230 payload="mens"
[CLIENTE] Enviando pacote seq=1768004231 payload="agem"
[CLIENTE] Enviando pacote seq=1768004232 payload=" de "
[CLIENTE] Enviando pacote seq=1768004233 payload="test"
[CLIENTE] ACK recebido: ack=1768004229
[CLIENTE] ACK recebido: ack=1768004230
[CLIENTE] ACK recebido: ack=1768004231
[CLIENTE] ACK recebido: ack=1768004232
[CLIENTE] ACK recebido: ack=1768004233
[SUCCESS] Lote enviado corretamente (ACK) time=1ms
[CLIENTE] Enviando pacote seq=1768004234 payload="e co"
[CLIENTE] Enviando pacote seq=1768004235 payload="m be"
...
[SUCCESS] Lote enviado corretamente (ACK) time=0ms
```

E o outro lado mostra os pacotes chegando e a mensagem montada:

```text
[SERVIDOR] Pacote recebido: seq=293991314 checksum=0xB32BDA43 payload="olá "
[SERVIDOR] Pacote recebido: seq=293991315 checksum=0x0B93B911 payload="mund"
[SERVIDOR] Pacote recebido: seq=293991316 checksum=0xB1BA164A payload="o, t"
[SERVIDOR] Pacote recebido: seq=293991317 checksum=0xEB70BBEE payload="udo "
[SERVIDOR] Pacote recebido: seq=293991318 checksum=0x9842D188 payload="bem?"
[SERVIDOR] Mensagem completa: "olá mundo, tudo bem?"
```

O mesmo vale no sentido contrário, quando o servidor envia para o cliente. Os
dois podem enviar ao mesmo tempo.

Os números de sequência são aleatórios e mudam a cada execução.

No modo `individual`, quem envia registra um
`[CLIENTE] ACK recebido: ack=...` seguido de
`[SUCCESS] Pacote enviado corretamente (ACK)` para cada pacote, e quem recebe
exibe os pacotes sem o payload.

### 4. Encerrando

Digite `sair` em qualquer um dos lados:

```text
[CLIENTE] FIN enviado (seq=293991319)
[CLIENTE] FIN-ACK recebido; conexão encerrada.
```

```text
[SERVIDOR] FIN recebido e confirmado; o outro lado encerrou a conexão.

server aguardando conexão em 0.0.0.0:2000 (Ctrl+C para encerrar)
```

Se o servidor digitar `sair`, o programa do cliente termina e o servidor volta a
aguardar novas conexões.

## Configurações aceitas

**Modo de operação:** `individual` ou `lote`

**Protocolo:** `GBN` (Go-Back-N) ou `SR` (Repetição Seletiva)

**Tamanho máximo do texto:** limite da mensagem inteira, mínimo de 30 caracteres

**Tamanho de cada pacote:** de 1 a 4 caracteres (limite do payload)

**Janela:** definida pelo servidor (valor inicial: 5)

## Cores no terminal

Os logs usam cores: azul para pacotes enviados, vermelho para avisos (timeout e
pacotes descartados), verde para confirmações e mensagens completas, e amarelo
para pacotes recebidos. No Windows, use o PowerShell ou o Windows Terminal.

## Observação

Esta implementação corresponde ao **Checkpoint 2 — Protocolo Sem Erros**.
O canal é considerado livre de erros e perdas, então somente o caminho sem erros
acontece. O tratamento de erros e perdas já está definido e implementado, e será
exercitado quando a simulação de falhas for adicionada nos próximos checkpoints.
