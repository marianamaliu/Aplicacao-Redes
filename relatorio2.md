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

O campo `payload` tem no **máximo 4 caracteres** (constante `TAMANHO_MAX_PAYLOAD`).
A mensagem do usuário pode ter até `max_texto` caracteres (mínimo de 30,
negociado no handshake), mas é sempre fragmentada em pacotes de até 4
caracteres: uma mensagem de 100 caracteres gera 25 pacotes. O remetente escolhe
o tamanho de cada pacote entre 1 e 4, e o destinatário trata como fora do
formato (e ignora) qualquer `DATA` com payload maior que 4.

Como os dois lados enviam e recebem, um `ACK` recebido sempre se refere a um
pacote `DATA` que o próprio lado enviou.

Cada `ACK` recebido é exibido pelo remetente assim que chega, com o número
confirmado: `[CLIENTE] ACK recebido: ack=<seq>`. No GBN o ACK é cumulativo (um
`ack` confirma todos os pacotes até aquele `seq`); no SR cada ACK confirma um
único pacote.

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

## Processo de Construção e Uso de IA

Durante o desenvolvimento deste checkpoint, utilizamos inteligência artificial
como apoio na revisão do código existente, na implementação da troca de
mensagens e na escrita da documentação.

A IA foi utilizada para revisar o handshake do checkpoint anterior, implementar
a troca de mensagens seguindo o padrão definido no `padrao_msgs.txt`, corrigir os
problemas encontrados durante os testes e explicar o funcionamento do código.

Todo o código foi executado e testado por nós em todas as combinações de modo e
protocolo, e cada problema encontrado nos testes foi levado de volta para
correção.

### Principais pontos em que a IA foi utilizada

* Revisão do handshake: validação do SYN-ACK no cliente, validação do modo no
  servidor e escolha dos parâmetros pelo usuário;
* Identificação do problema na leitura do socket, que descartava mensagens
  recebidas juntas, e criação da leitura com buffer;
* Ajudou na Implementação da troca de mensagens: divisão em pacotes, checksum CRC32,
  janela, Go-Back-N, Repetição Seletiva, timeout e encerramento com FIN;
* Envio de várias mensagens na mesma conexão e servidor ativo após a saída do
  cliente;
* Transformação da comunicação em chat, com threads e o arquivo `protocolo.py`;
* Testes, incluindo a simulação de perdas para verificar as retransmissões;
* Atualização do `relatorio2.md` e do `README.md`

### Análise crítica e debugging

Problemas encontrados ao revisar o código contra o enunciado e ao executar
cliente e servidor nas quatro combinações (individual/lote × GBN/SR). A IA foi
usada como apoio para revisar, testar e propor correções; cada alteração foi
aplicada, compreendida e validada pelo grupo.

**1. Payload maior que 4 caracteres.** O tamanho de cada pacote podia ser
qualquer valor até `max_texto`, confundindo o limite da mensagem inteira com o
limite do pacote. Com `max_texto = 100`, uma mensagem de 100 caracteres saía em
um único pacote, contra o enunciado (máximo de 4). Na revisão feita com apoio de
IA, um teste com tamanho de pacote 30 mostrou o problema. Aplicamos a correção: 
constante `TAMANHO_MAX_PAYLOAD = 4` em três pontos, `pedir_tamanho`
(entrada do usuário), `montar_pacotes` (criação do pacote) e `pacote_valido`
(recepção). Verificação: uma mensagem de 100 caracteres passou a gerar 25
pacotes de 4.

**2. `KeyError` ao exibir o ACK recebido.** Ao adaptar a sugestão de exibir o
`ACK recebido` no cliente, a linha foi colocada em `_receber` fora do
`if tipo == "ACK"`. Pacotes `DATA`, `FIN` e `FIN_ACK` não têm o campo `ack`,
então `mensagem['ack']` gerou `KeyError`. Esse erro não é capturado pelo
`except (ConnectionError, ValueError, OSError)`, a thread de recepção morreu
sem aviso, o servidor nunca montou a mensagem e o cliente ficou retransmitindo
por timeout. O problema foi identificado ao rodar as quatro combinações e ler o
traceback no servidor. Correção: manter a linha somente dentro do
`if tipo == "ACK"`.

**3. Leitura do socket.** A primeira leitura de mensagens descartava o que
chegava junto no mesmo `recv` depois do `\n`. Correção: um buffer por conexão
(`LeitorMensagens`), que guarda o excedente para a leitura seguinte.

**4. Encerramento após uma mensagem.** A primeira versão da troca de mensagens
terminava a execução depois de enviar uma. O grupo percebeu nos testes, e a
correção permitiu várias mensagens na mesma conexão e manteve o servidor ativo
depois que o cliente sai.

Em todos os casos, a correção foi validada executando cliente e servidor reais
nas quatro combinações de modo e protocolo, nos dois sentidos de envio.

### Prompts utilizados

1. Esse é o que temos que fazer no checkpoint 2 e essa foi a mensagem da minha
   dupla. Verifique o que já foi feito no repositório e me diga o que eu tenho
   que fazer.

2. Verifique se está tudo certo no handshake e corrija as inconsistências
   apontadas.

3. Com base em tudo que te passei, isso tudo está dentro da entrega 2?

4. Deixamos passar um bug: o programa não pode encerrar quando a mensagem é
   enviada, ele tem que continuar.

5. O servidor também tem que enviar mensagem. Os dois devem poder enviar a
   qualquer momento, como num chat.

6. No modo lote, cada lote tem que ser verificado antes de enviar outro.

7. Por que o cliente diminuiu tanto de tamanho?

8. Como faço para testar?

9. Verifique se a entrega esta ok para ser submetida sem erros.


### Decisões tomadas a partir das respostas da IA

Para cada prompt utilizado, o que decidimos a partir da resposta recebida.

**1. Levantamento do que fazer no checkpoint 2.** A resposta mostrou que o
handshake e o `padrao_msgs.txt` já estavam prontos e que faltava a troca de
mensagens. Decidimos concentrar o trabalho nela, aproveitando o que já existia.

**2. Revisão do handshake.** Para corrigir as inconsistências, decidimos usar
`seq` inicial aleatório (como no TCP), validar o campo `modo` (que muda a forma
de enviar) e deixar o usuário escolher os parâmetros. Decidimos também commitar o
handshake revisado antes de seguir e manter o código e os comentários originais,
retirando os comentários longos sugeridos pela IA.

**3. O que cabe na entrega 2.** Decidimos implementar o protocolo completo
(checksum CRC32, campo `fim` para marcar o último pacote, janela, GBN, SR,
timeout e encerramento), mesmo com o canal sem erros, deixando o tratamento de
falhas pronto para os próximos checkpoints.

**4. Programa encerrando após uma mensagem.** Decidimos que o programa só termina
quando o usuário digita `sair`. Com isso, o tamanho do pacote passou a ser
perguntado a cada mensagem, a numeração de `seq` continua entre mensagens e o
servidor volta a aguardar novos clientes.

**5. Servidor também enviando mensagens.** Entre só o cliente enviar, o servidor
responder por turnos ou os dois enviarem a qualquer momento, escolhemos a
terceira opção, como num chat. Para isso, decidimos usar threads, filas e uma
trava no socket, separar o código comum no `protocolo.py`, definir o formato
`FIN`/`FIN_ACK` e ativar `TCP_NODELAY`.

**6. Verificação de cada lote.** Decidimos que, no modo lote, cada lote só é
enviado depois que todos os pacotes do lote anterior forem confirmados.

**7. Redução do tamanho do cliente.** A resposta explicou que o código comum foi
movido para o `protocolo.py`. Decidimos manter o handshake em cada arquivo, por
ser diferente para cada lado, e priorizar entender o código linha por linha, em
vez de um roteiro de apresentação.

**8. Como testar.** Decidimos testar as quatro combinações de modo e protocolo,
nos dois sentidos de envio, e simular perdas para verificar as retransmissões.

**9. Revisão final da entrega.** Decidimos revisar o código contra o enunciado
antes de submeter, o que levou às correções descritas na análise crítica abaixo.
