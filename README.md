*README EXPLICANDO COMO RODAR O PROJETO(O OUTRO EQUIVALE AO RELATORIO)*

# Trabalho de Redes — Checkpoint 1

Aplicação cliente-servidor desenvolvida em Python utilizando sockets TCP.

Nesta primeira entrega foi implementada a conexão entre cliente e servidor e o handshake inicial da aplicação.

## Requisitos

Para executar o projeto é necessário:

- Python 3 instalado
- Dois terminais abertos na pasta do projeto

Não é necessário instalar nenhuma biblioteca externa. O projeto utiliza apenas módulos da biblioteca padrão do Python, como `socket` e `json`.

## Arquivos principais

- `servidor.py` — inicia o servidor, recebe o handshake, valida os parâmetros e envia a resposta.
- `cliente.py` — conecta ao servidor, envia o handshake e recebe a confirmação.

## Como executar

O servidor e o cliente devem ser executados separadamente.

Para isso, abra **dois terminais na pasta do projeto**.

### 1. Primeiro terminal — Servidor

No primeiro terminal, execute:

```bash
python servidor.py
```

Após executar o comando, deverá aparecer:

```text
server aguardando conexão em 0.0.0.0:2000
```

O terminal ficará aguardando a conexão de um cliente.

**Mantenha esse terminal aberto.**

### 2. Segundo terminal — Cliente

Sem fechar o terminal do servidor, abra um **segundo terminal** na mesma pasta do projeto.

Execute:

```bash
python cliente.py
```

O cliente irá se conectar ao servidor automaticamente utilizando:

```text
IP: 127.0.0.1
Porta: 2000
```

Após a conexão, o cliente envia o handshake para o servidor.

### 3. Resultado esperado

No terminal do servidor deverá aparecer algo semelhante a:

```text
server aguardando conexão em 0.0.0.0:2000

Cliente conectado: ('127.0.0.1', XXXXX)
Mensagem recebida:
{'tipo': 'HANDSHAKE', 'modo': 'lote', 'protocolo': 'GBN', 'max_texto': 100}

Handshake valido
resposta enviada ao cliente
```

O valor `XXXXX` representa a porta utilizada pelo cliente e pode mudar a cada execução.

No terminal do cliente deverá aparecer:

```text
conectado ao server 127.0.0.1:2000
Handshake enviado
Handshake aprovado pelo servidor.
Modo: lote
Protocolo: GBN
Tamanho máximo do texto: 100
Tamanho da janela: 5
```

Quando essas mensagens forem apresentadas, significa que a conexão e o handshake foram realizados corretamente.

## Funcionamento do Handshake

O fluxo da comunicação é:

```text
SERVIDOR
   |
   | Aguarda conexão
   |
   | <---------------- Cliente conecta
   |
   | <---------------- HANDSHAKE
   |
   | Valida os parâmetros
   |
   | ----------------> HANDSHAKE_ACK
   |
CLIENTE recebe a confirmação
```

O cliente envia no handshake:

- Modo de operação: `lote`
- Protocolo: `GBN` (Go-Back-N)
- Tamanho máximo do texto: `100`

O servidor valida essas informações e define:

- Tamanho inicial da janela: `5`

Em seguida, o servidor envia um `HANDSHAKE_ACK` para informar ao cliente que a configuração foi aceita.

## Configurações aceitas

O servidor está preparado para reconhecer:

**Modo de operação:**
- `individual`
- `lote`

**Protocolo:**
- `GBN` — Go-Back-N
- `SR` — Selective Repeat

**Tamanho do texto:**
- mínimo de 30 caracteres

**Janela:**
- definida pelo servidor
- valor inicial: 5

## Observação

Esta implementação corresponde ao **Checkpoint 1 — Handshake & Sockets**.

O objetivo desta etapa é estabelecer a comunicação inicial entre cliente e servidor e realizar a troca dos parâmetros necessários para iniciar o protocolo.

As funcionalidades de transferência confiável de dados serão implementadas incrementalmente nos próximos checkpoints.