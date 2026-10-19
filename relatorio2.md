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

Depois do handshake, o cliente pede a mensagem (que não pode passar de
`max_texto`) e o tamanho de cada pacote, em caracteres. Ao terminar o envio,
volta a pedir uma nova mensagem; digitar `sair` encerra a conexão.

## Formato dos segmentos de dados

Todos os segmentos são objetos JSON terminados em `\n`.

| Segmento | Sentido | Campos |
|---|---|---|
| `DATA` | cliente → servidor | `seq`, `payload` (trecho do texto), `checksum`, `fim` |
| `ACK` | servidor → cliente | `ack` (número de sequência confirmado) |
| `FIN` | cliente → servidor | `seq` (próximo número após o último pacote) |
| `FIN_ACK` | servidor → cliente | `ack = seq do FIN + 1` |

Exemplo de pacote de dados:

```json
{"tipo": "DATA", "seq": 293991314, "payload": "olá ", "checksum": 3005995587, "fim": false}
```

O campo `fim` é `true` apenas no último pacote de cada mensagem. É ele que
indica ao servidor onde uma mensagem termina e a próxima começa.

### Números de sequência

O primeiro pacote de dados usa `seq = client_isn + 1`, o mesmo valor do ACK
final do handshake (como no TCP, o ACK puro não consome número de sequência).
Cada pacote seguinte incrementa o `seq` em 1, de forma circular. A numeração
continua entre as mensagens da mesma conexão: se a primeira mensagem terminou no
`seq` 10, a segunda começa no 11.

### Checksum

O checksum é o CRC32 do `payload` codificado em UTF-8 (`zlib.crc32`). O cliente
calcula e envia junto com o pacote; o servidor recalcula e compara. Se os valores
forem diferentes, o pacote é considerado corrompido e descartado sem ACK (no GBN,
o servidor reenvia o ACK do último pacote recebido em ordem).

## Modos de operação

- **Individual (isolado):** o cliente envia um pacote e só envia o próximo
  depois de receber o ACK dele (janela efetiva = 1). Cada confirmação é
  registrada com o tempo de ida e volta.
- **Lote:** o cliente envia até `janela` pacotes seguidos sem esperar
  confirmação. Quando todos os pacotes da mensagem são confirmados, registra o
  tempo total do lote.

## Protocolos de retransmissão

### Go-Back-N (GBN)

- **Cliente:** mantém um único temporizador, referente ao pacote mais antigo
  ainda sem confirmação (`base`). Se ele expirar, reenvia esse pacote e todos os
  que foram enviados depois dele.
- **Servidor:** só aceita o pacote com o próximo `seq` esperado. Pacotes fora de
  ordem são descartados. O ACK é cumulativo: o servidor sempre responde com o
  `seq` do último pacote recebido em ordem, confirmando todos os anteriores.

### Repetição Seletiva (SR)

- **Cliente:** mantém um temporizador por pacote. Quando um expira, reenvia
  apenas aquele pacote. A janela avança quando o pacote da `base` é confirmado.
- **Servidor:** aceita pacotes fora de ordem que estejam dentro da janela,
  guarda-os em um buffer e confirma cada um individualmente. Os trechos são
  entregues em ordem assim que as lacunas são preenchidas. Pacotes repetidos
  (já entregues) são confirmados de novo, para o caso de o ACK anterior ter se
  perdido.

O tempo limite (`TIMEOUT`) é de 1 segundo.

## Várias mensagens na mesma conexão

Depois do handshake, o cliente pode enviar quantas mensagens quiser sem abrir uma
nova conexão. Para cada mensagem, o servidor junta os trechos em ordem e, ao
entregar o pacote marcado com `fim: true`, imprime a mensagem completa e passa a
montar a próxima.

## Encerramento

Quando o usuário digita `sair`, o cliente envia `FIN` com o `seq` seguinte ao
último pacote enviado. O servidor confere se recebeu tudo até ali, responde com
`FIN_ACK` e fecha a conexão. Se o `FIN_ACK` não chegar dentro do tempo limite, o
cliente reenvia o `FIN` (até 5 tentativas).

O servidor continua rodando depois que um cliente se desconecta e volta a
aguardar novas conexões, atendendo um cliente por vez. Ele é encerrado com
Ctrl+C.

## Escopo deste checkpoint

Neste checkpoint o canal é considerado livre de erros e perdas, então apenas o
caminho sem erros acontece: todos os pacotes chegam em ordem, nenhum checksum
falha e nenhum temporizador expira. O tratamento de timeout, retransmissão,
pacotes corrompidos e pacotes fora de ordem já está implementado e definido
acima, e será exercitado quando a simulação de erros for adicionada.