# Aplicacao-Redes
Handshake precisou ser atualizado, pois não seguia o padrão de SYN, SEQ e ACK os 
quais permitem a validação do handshake

## Handshake de três vias

O cliente e o servidor estabelecem os parâmetros iniciais em três segmentos JSON,
delimitados por `\n`, antes da troca de mensagens de dados:

1. **SYN — cliente → servidor:** `syn: 1`, `seq: client_isn` e `ack: 0`, junto
   dos parâmetros solicitados (`modo`, `protocolo` e `max_texto`).
2. **SYN-ACK — servidor → cliente:** `syn: 1`, `seq: server_isn` e
   `ack: client_isn + 1`. Se os parâmetros forem aceitos, a resposta inclui
   `status: "OK"`, os valores negociados e o tamanho da janela. Caso contrário,
   a resposta traz `status: "ERRO"` e o `motivo` da recusa.
3. **ACK — cliente → servidor:** `syn: 0`, `seq: client_isn + 1` e
   `ack: server_isn + 1`. O servidor valida os dois números antes de considerar
   o handshake concluído.

Os números de sequência iniciais são aleatórios de 32 bits; o incremento é
circular (após 2³² − 1 volta para 0).

### Validações

- **Servidor:** confere `tipo`, `syn`, `seq` (inteiro de 32 bits), `ack = 0`,
  `modo` (`individual` ou `lote`), `protocolo` (`GBN` ou `SR`) e `max_texto`
  (mínimo de 30). No ACK final, confere se `seq` e `ack` são os esperados.
- **Cliente:** confere `tipo`, `syn`, `status`, o `seq` do servidor, se
  `ack = client_isn + 1`, se os parâmetros devolvidos são os mesmos que foram
  pedidos e se a janela é válida.

Mensagens fora do formato JSON ou que não sejam objetos encerram a conexão com
uma mensagem de erro, sem derrubar o programa.

### Leitura das mensagens

Como o TCP é um fluxo de bytes, várias mensagens podem chegar juntas em uma
única leitura do socket. Cada lado mantém um buffer e só entrega uma mensagem
quando encontra o `\n`; o que sobrar fica guardado para a leitura seguinte.
Assim nenhuma mensagem é descartada.

## Parâmetros escolhidos pelo usuário

Antes de conectar, o cliente pergunta:

- **Modo de operação:** `individual` (isolado) ou `lote`
- **Protocolo:** `GBN` (Go-Back-N) ou `SR` (Repetição Seletiva)
- **Tamanho máximo do texto:** em caracteres

Esses parâmetros valem para os dois sentidos da comunicação. Depois do
handshake, cliente e servidor funcionam como um chat: qualquer um dos dois pode
digitar uma mensagem (que não pode passar de `max_texto`) e, em seguida, o
tamanho de cada pacote, em caracteres. Digitar `sair` encerra a conexão.

## Formato dos segmentos de dados

Todos os segmentos são objetos JSON terminados em `\n`.

| Segmento | Sentido | Campos |
|---|---|---|
| `DATA` | remetente → destinatário | `seq`, `payload` (trecho do texto), `checksum`, `fim` |
| `ACK` | destinatário → remetente | `ack` (número de sequência confirmado) |
| `FIN` | quem encerra → o outro lado | `seq` (próximo número após o último pacote enviado) |
| `FIN_ACK` | o outro lado → quem encerra | `ack = seq do FIN + 1` |

Exemplo de pacote de dados:

```json
{"tipo": "DATA", "seq": 293991314, "payload": "olá ", "checksum": 3005995587, "fim": false}
```

O campo `fim` é `true` apenas no último pacote de cada mensagem. É ele que
indica ao destinatário onde uma mensagem termina e a próxima começa.

Como os dois lados enviam e recebem, um `ACK` recebido sempre se refere a um
pacote `DATA` que o próprio lado enviou.

### Números de sequência

Cada sentido da comunicação tem a sua própria numeração, como no TCP:

- **Cliente → servidor:** começa em `client_isn + 1`, o mesmo valor do ACK final
  do handshake (o ACK puro não consome número de sequência).
- **Servidor → cliente:** começa em `server_isn + 1`.

Cada pacote seguinte incrementa o `seq` em 1, de forma circular. A numeração
continua entre as mensagens da mesma conexão: se a primeira mensagem terminou no
`seq` 10, a segunda começa no 11.

### Checksum

O checksum é o CRC32 do `payload` codificado em UTF-8 (`zlib.crc32`). O
remetente calcula e envia junto com o pacote; o destinatário recalcula e compara.
Se os valores forem diferentes, o pacote é considerado corrompido e descartado
sem ACK (no GBN, o destinatário reenvia o ACK do último pacote recebido em ordem).

## Modos de operação

O modo e o protocolo escolhidos no handshake valem para quem estiver enviando,
seja o cliente ou o servidor.

- **Individual (isolado):** o remetente envia um pacote e só envia o próximo
  depois de receber o ACK dele (janela efetiva = 1). Cada confirmação é
  registrada com o tempo de ida e volta.
- **Lote:** a mensagem é dividida em lotes de até `janela` pacotes (5). O
  remetente envia todos os pacotes de um lote sem esperar confirmação e só envia
  o lote seguinte depois que **todos** os pacotes do lote atual forem
  confirmados. Ao fim de cada lote, registra `[SUCCESS] Lote enviado
  corretamente (ACK)` com o tempo daquele lote. Uma mensagem de 16 pacotes, por
  exemplo, é enviada em 4 lotes (5 + 5 + 5 + 1).

## Protocolos de retransmissão

### Go-Back-N (GBN)

- **Remetente:** mantém um único temporizador, referente ao pacote mais antigo
  ainda sem confirmação (`base`). Se ele expirar, reenvia esse pacote e todos os
  que foram enviados depois dele.
- **Destinatário:** só aceita o pacote com o próximo `seq` esperado. Pacotes fora
  de ordem são descartados. O ACK é cumulativo: o destinatário sempre responde
  com o `seq` do último pacote recebido em ordem, confirmando todos os anteriores.

### Repetição Seletiva (SR)

- **Remetente:** mantém um temporizador por pacote. Quando um expira, reenvia
  apenas aquele pacote.
- **Destinatário:** aceita pacotes fora de ordem que estejam dentro da janela,
  guarda-os em um buffer e confirma cada um individualmente. Os trechos são
  entregues em ordem assim que as lacunas são preenchidas. Pacotes repetidos
  (já entregues) são confirmados de novo, para o caso de o ACK anterior ter se
  perdido.

Em ambos os protocolos, as retransmissões acontecem dentro do lote atual: o
próximo lote só começa quando todos os pacotes do lote atual forem confirmados.

O tempo limite (`TIMEOUT`) é de 1 segundo.

## Chat: os dois lados enviam a qualquer momento

Depois do handshake, cliente e servidor podem enviar quantas mensagens quiserem,
a qualquer momento e ao mesmo tempo, sem abrir uma nova conexão. Para isso, cada
lado usa linhas de execução (threads) separadas:

- **Thread principal:** recebe o que foi digitado e envia as mensagens,
  controlando a janela, os temporizadores e as retransmissões.
- **Thread de recebimento:** lê continuamente o socket. Pacotes `DATA` são
  conferidos, confirmados com `ACK` e montados; ao entregar o pacote marcado com
  `fim: true`, a mensagem completa é exibida. `ACK` e `FIN_ACK` recebidos são
  repassados à thread principal por filas.
- **Thread do teclado:** lê o que o usuário digita e coloca em uma fila, para
  que o programa possa reagir ao fim da conexão mesmo enquanto espera a próxima
  mensagem.

Uma trava garante que as threads não escrevam no socket ao mesmo tempo, o que
misturaria os bytes de duas mensagens JSON.

O código comum aos dois lados (formato dos pacotes, checksum, envio com GBN/SR,
recebimento e encerramento) fica no arquivo `protocolo.py`, usado pelo
`cliente.py` e pelo `servidor.py`. O handshake continua em cada um dos arquivos,
porque é diferente para cada lado.

## Encerramento

Qualquer um dos lados pode encerrar a conexão digitando `sair`. Quem encerra
envia `FIN` com o `seq` seguinte ao último pacote que enviou. O outro lado confere
se recebeu tudo até ali, responde com `FIN_ACK` e fecha a conexão. Se o `FIN_ACK`
não chegar dentro do tempo limite, o `FIN` é reenviado (até 5 tentativas).

Quando o servidor encerra a conexão, o programa do cliente termina. Quando o
cliente encerra, o servidor continua rodando e volta a aguardar novas conexões,
atendendo um cliente por vez. O servidor é encerrado com Ctrl+C.

## Escopo deste checkpoint

Neste checkpoint o canal é considerado livre de erros e perdas, então apenas o
caminho sem erros acontece: todos os pacotes chegam em ordem, nenhum checksum
falha e nenhum temporizador expira. O tratamento de timeout, retransmissão,
pacotes corrompidos e pacotes fora de ordem já está implementado e definido
acima, e será exercitado quando a simulação de erros for adicionada.