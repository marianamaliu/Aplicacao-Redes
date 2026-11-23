## Checkpoint 3 – Inserção de Erros e Perdas

Alunos: Felipe Lemos, Diego Gomes, Natan Luís, Sophia Brito, Felipe Braz, Mariana Maliu, Arthur Coelho, Daniel Bezerra e Luana Fernandes

---

## 1. Introdução

No checkpoint 2, o protocolo ficou completamente definido, mas o canal era
considerado perfeito: nenhum pacote se perdia, nenhum chegava corrompido e
nenhum temporizador expirava. O tratamento de erros existia no código, mas
nunca era executado.

Neste último checkpoint, o objetivo foi **inserir erros e perdas simulados** e
mostrar que o protocolo se recupera corretamente de cada um deles. Além disso,
completamos os itens do transporte confiável que ainda faltavam e
implementamos os dois algoritmos da pontuação extra:

* **Simulador de falhas** determinístico, definido no lado cliente: perda de
  pacote, corrupção de pacote e perda de ACK;
* **Reconhecimento negativo (NACK)**, que ainda não existia no protocolo;
* **Janela de 1 a 5 controlada pelo servidor** durante a conexão (antes era
  fixa em 5);
* **Checksum CRC-16 implementado à mão**, substituindo o `zlib.crc32`
  (pontuação extra 1);
* **Criptografia simétrica com XOR implementada à mão** para a troca de
  mensagens (pontuação extra 2).

Com isso, todas as características do transporte confiável da tabela 3.1 do
livro podem ser verificadas na aplicação:

| Característica | Como aparece no protocolo |
|---|---|
| Soma de verificação | CRC-16 de cada pacote, conferido pelo destinatário |
| Temporizador | `TIMEOUT` de 1 segundo; o remetente reenvia quando ele expira |
| Número de sequência | `seq` de 32 bits, aleatório no handshake e incrementado a cada pacote |
| Reconhecimento positivo | segmento `ACK` (cumulativo no GBN, individual no SR) |
| Reconhecimento negativo | segmento `NACK`, enviado ao detectar um pacote corrompido |
| Janela, paralelismo | envio em lote de até `janela` pacotes, com a janela (1 a 5) definida pelo servidor |

---

## 2. Especificação do protocolo (versão final)

### 2.1 Handshake

O handshake de três vias não mudou em relação ao checkpoint 2:

1. **SYN (cliente → servidor):** `syn: 1`, `seq: client_isn`, `ack: 0`, `modo`,
   `protocolo` e `max_texto`.
2. **SYN-ACK (servidor → cliente):** `syn: 1`, `seq: server_isn`,
   `ack: client_isn + 1`, `status`, os parâmetros aceitos e a `janela` inicial
   (5). Em caso de recusa, `status: "ERRO"` e o `motivo`.
3. **ACK (cliente → servidor):** `syn: 0`, `seq: client_isn + 1`,
   `ack: server_isn + 1`.

A única mudança é que agora o cliente também recusa um SYN-ACK cuja janela não
esteja entre 1 e 5.

### 2.2 Segmentos

Todos os segmentos são objetos JSON terminados em `\n`.

| Segmento | Sentido | Campos | Função |
|---|---|---|---|
| `DATA` | remetente → destinatário | `seq`, `payload`, `checksum`, `fim` | carrega um trecho da mensagem (cifrado) |
| `ACK` | destinatário → remetente | `ack` | confirma o pacote com aquele `seq` |
| `NACK` | destinatário → remetente | `nack` | **novo:** avisa que o pacote com aquele `seq` chegou corrompido |
| `JANELA` | servidor → cliente | `janela` | **novo:** novo tamanho da janela de envio do cliente (1 a 5) |
| `FIN` | quem encerra → outro lado | `seq` | pedido de encerramento |
| `FIN_ACK` | outro lado → quem encerra | `ack = seq do FIN + 1` | confirma o encerramento |

Exemplo de pacote `DATA` na versão final:

```json
{"tipo": "DATA", "seq": 3808809747, "payload": "1905a7c044", "checksum": 56944, "fim": false}
```

O `payload` não é mais o texto do usuário, e sim o texto **cifrado e
convertido para hexadecimal** (seção 4). O texto original continua limitado a
**4 caracteres por pacote**, como pede o enunciado. Como cada caractere pode
ocupar até 4 bytes em UTF-8 e cada byte vira 2 caracteres em hexadecimal, o
campo `payload` aceita até 32 caracteres.

### 2.3 Ordem de processamento de um pacote

```text
Remetente:     texto (até 4 caracteres)
                 → bytes (UTF-8)
                 → cifra XOR (deslocamento = seq)
                 → hexadecimal
                 → CRC-16 sobre o hexadecimal
                 → envia

Destinatário:  recebe
                 → recalcula o CRC-16 e compara
                     ├─ diferente → descarta e envia NACK
                     └─ igual     → hexadecimal → bytes → decifra (mesmo seq) → texto
                                     → entrega (GBN ou SR) e envia ACK
```

O checksum é calculado **sobre o texto cifrado** porque ele protege o que
viaja no canal. Assim o destinatário confere a integridade antes de decifrar:
um pacote corrompido é descartado sem nem tentar decifrar.

---

## 3. Checksum CRC-16 implementado à mão (pontuação extra 1)

Até o checkpoint 2, o checksum era o CRC-32 da biblioteca `zlib`. Para a
pontuação extra, substituímos por um **CRC-16/CCITT escrito por nós**, sem
nenhuma biblioteca. O `import zlib` foi removido do projeto.

### 3.1 Fundamento matemático

O CRC é o **resto da divisão** dos bits da mensagem por um polinômio gerador,
em aritmética módulo 2, na qual somar e subtrair são a mesma operação: o XOR.
Se algum bit da mensagem mudar no caminho, o resto muda e o destinatário
percebe.

Exemplo pequeno, com os dados `1101` e o gerador `1011` (x³ + x + 1):

```text
1101000      ← dados + 3 zeros (grau do gerador)
1011         → XOR → 0110000
 1011        → XOR → 0011100
  1011       → XOR → 0001010
   1011      → XOR → 0000001
resto = 001  → envia 1101 001
```

O destinatário divide `1101001` pelo mesmo gerador. Se o resto for `000`, os
dados estão íntegros.

Parâmetros usados (CRC-16/CCITT):

| Parâmetro | Valor | Significado |
|---|---|---|
| Gerador | `0x1021` | x¹⁶ + x¹² + x⁵ + 1 (o termo x¹⁶ fica implícito) |
| Valor inicial | `0xFFFF` | evita que mensagens que começam com zeros tenham CRC 0 |

### 3.2 Implementação

```python
def crc16(dados):
    registrador = 0xFFFF
    for byte in dados:
        registrador ^= (byte << 8)
        for _ in range(8):
            if registrador & 0x8000:
                registrador = (registrador << 1) ^ 0x1021
            else:
                registrador = (registrador << 1)
            registrador &= 0xFFFF
    return registrador
```

| Linha | Papel na divisão |
|---|---|
| `registrador ^= (byte << 8)` | coloca o próximo byte nos 8 bits de cima, onde a divisão começa |
| `if registrador & 0x8000` | o bit mais alto é 1? Então o divisor "cabe" |
| `(registrador << 1) ^ 0x1021` | desce uma casa e subtrai (XOR) o gerador |
| `registrador << 1` | o divisor não cabe: só desce uma casa |
| `registrador &= 0xFFFF` | mantém 16 bits. Em Python os inteiros não têm limite; o bit 16 que cai fora é o x¹⁶ implícito |

### 3.3 Validação

* `crc16(b"123456789")` resulta em `0x29B1`, o valor de referência conhecido
  do CRC-16/CCITT-FALSE;
* `crc16("olá ".encode())` resulta em `0x0E43`;
* comparamos o resultado com a implementação de referência em 200 entradas
  aleatórias, e todas coincidiram;
* nos testes de corrupção, o servidor passou a mostrar o checksum de 4 dígitos
  (`checksum recebido=0x7D03, calculado=0x3AD0`).

---

## 4. Criptografia simétrica com XOR (pontuação extra 2)

### 4.1 Fundamento matemático

Cada byte da mensagem passa por XOR com um byte da chave:

```text
c[i] = p[i] ⊕ k[(s + i) mod n]
```

| Símbolo | Significado | No código |
|---|---|---|
| `p[i]` | byte `i` do texto original | `b` |
| `k` | chave pré-compartilhada | `CHAVE` |
| `n` | tamanho da chave | `len(CHAVE)` |
| `s` | deslocamento, igual ao `seq` do pacote | `deslocamento` |
| `⊕` | XOR | `^` |

O XOR se desfaz sozinho: `(p ⊕ k) ⊕ k = p ⊕ (k ⊕ k) = p ⊕ 0 = p`. Por isso
**a mesma função cifra e decifra**, e é isso que caracteriza uma cifra
simétrica.

Exemplo com a letra `o` e a chave `K`:

```text
'o' = 0x6F = 0110 1111
'K' = 0x4B = 0100 1011
XOR        = 0010 0100 = 0x24   ← cifrado
0x24 ⊕ 'K' = 0110 1111 = 'o'    ← decifrado
```

### 4.2 Implementação

```python
CHAVE = b"AtividadeRedes01"

def aplicar_xor(dados, deslocamento):
    resultado = []
    for i, b in enumerate(dados):
        byte_chave = CHAVE[(deslocamento + i) % len(CHAVE)]
        resultado.append(b ^ byte_chave)
    return bytes(resultado)
```

Decisões tomadas:

* **Chave de 16 bytes.** A primeira versão tinha uma chave de 1 byte
  (`b"x"`). Com ela, o `% len(CHAVE)` sempre dava 0, o deslocamento não tinha
  efeito e a cifra virava uma cifra de César com apenas 256 chaves possíveis.
* **Deslocamento pelo `seq`.** Sem ele, todo pacote começaria no primeiro
  byte da chave: com payloads de até 4 caracteres, só o começo da chave seria
  usado e pacotes com o mesmo texto gerariam o mesmo cifrado. Com o `seq`,
  cada pacote começa em um ponto diferente da chave. O destinatário consegue
  repetir a conta porque o `seq` viaja sem cifra.
* **Conversão para hexadecimal.** O resultado do XOR são bytes arbitrários,
  que podem não formar texto UTF-8 válido, e o JSON só transporta texto. Por
  isso o cifrado é enviado em hexadecimal (`bytes.hex()` /
  `bytes.fromhex()`, que são apenas conversões de formato).
* **Falha ao decifrar não derruba a conexão.** Se o hexadecimal for inválido
  ou o resultado não for UTF-8, o `ValueError` é capturado em `_tratar_dado`:
  o pacote é descartado e um `NACK` é enviado. Sem esse tratamento, o erro
  subiria até a thread de recepção e encerraria a conexão.

A cifra funciona nos dois sentidos (cliente → servidor e servidor → cliente),
porque fica no código comum, o `protocolo.py`.

No modo lote, o destinatário mostra o pacote como chegou e o texto decifrado:

```text
[SERVIDOR] Pacote recebido: seq=3808809747 checksum=0xDE70 cifrado=1905a7c044 payload="olá "
[SERVIDOR] Pacote recebido: seq=3808809748 checksum=0xAA4A cifrado=04110f00 payload="mund"
```

### 4.3 Limitações

A chave é pré-compartilhada e fica fixa no código dos dois lados. Quem tiver
acesso ao código consegue decifrar as mensagens. Um XOR com chave repetida
também é vulnerável a análise estatística quando há muito texto cifrado com a
mesma chave. Para este trabalho, o objetivo é demonstrar o funcionamento de
uma cifra simétrica; uma aplicação real usaria AES e uma troca de chaves como
Diffie-Hellman.

---

## 5. Simulador de erros e perdas

### 5.1 Funcionamento

Como o TCP por baixo da aplicação nunca perde nem corrompe dados, as falhas
são simuladas na camada de aplicação. O erro é **determinístico e definido no
lado cliente**, como pede o enunciado. Depois de digitar a mensagem e o
tamanho de cada pacote, o cliente pergunta:

```text
[CLIENTE] Simulação de falhas: a mensagem terá 5 pacotes (índices 0 a 4).
[CLIENTE] Pacotes a PERDER (ex: 1,3 | Enter para nenhum):
[CLIENTE] Pacotes a CORROMPER (ex: 1,3 | Enter para nenhum):
[CLIENTE] ACKs a PERDER (ex: 1,3 | Enter para nenhum):
```

Os pacotes são escolhidos pelo **índice dentro da mensagem** (0, 1, 2...), e
não pelo `seq`, porque o `seq` é aleatório.

| Falha | Como é simulada | Quem detecta | Recuperação |
|---|---|---|---|
| Perda de pacote | o remetente não envia o pacote ao socket | ninguém: o pacote "some" | timeout e reenvio |
| Corrupção de pacote | o remetente envia uma **cópia** com o primeiro caractere do `payload` alterado (`04110f00` → `14110f00`) | o servidor, pelo CRC-16 | NACK e reenvio imediato |
| Perda de ACK | o ACK chega, mas o remetente o descarta antes de processar | ninguém | timeout e reenvio; o destinatário reconhece o duplicado |

Pontos importantes da implementação:

* **Cada falha é aplicada uma única vez.** Depois de usada, ela sai do
  conjunto de falhas. Assim a retransmissão passa limpa; sem isso, o pacote
  falharia para sempre e o envio nunca terminaria.
* **A corrupção altera uma cópia.** O pacote original continua guardado na
  lista de pacotes, intacto, para ser usado na retransmissão.
* **O destinatário diferencia duplicado de fora de ordem.** Um pacote com
  `seq` menor que o esperado é um **duplicado** (já foi entregue); um maior
  que o esperado está **fora de ordem** (chegou adiantado).

### 5.2 Reconhecimento negativo (NACK)

No checkpoint 2, um pacote corrompido era apenas descartado, e o remetente
só descobria o problema quando o temporizador expirava (1 segundo depois).
Agora o destinatário responde na hora com `{"tipo": "NACK", "nack": <seq>}`,
e o remetente reenvia imediatamente:

* **GBN:** reenvia do pacote corrompido até o último enviado, porque o
  destinatário GBN descarta tudo o que chega depois de um pacote ruim;
* **SR:** reenvia só o pacote corrompido, porque os outros já estão no buffer
  do destinatário;
* um NACK de um pacote já confirmado é ignorado.

**NACK × timeout:** o NACK só existe se o pacote **chegou** (corrompido). Se
ele se perdeu, o destinatário nem sabe que ele existiu e não tem como pedir
de volta; esse caso continua sendo resolvido pelo temporizador, que também
cobre a perda do próprio NACK.

| Situação | Quem resolve | Tempo medido nos testes |
|---|---|---|
| Pacote corrompido | NACK | ~2 ms |
| Pacote perdido | timeout | ~1000 ms |
| ACK perdido (SR) | timeout | ~1000 ms |
| ACK perdido (GBN, não sendo o último) | o próximo ACK cumulativo | 0 ms (sem reenvio) |

### 5.3 Janela de 1 a 5 controlada pelo servidor

O enunciado define que a janela "vai variar de 1 a 5, sendo determinada pelo
servidor e com valor inicial de 5". O handshake continua anunciando 5, e
agora o servidor pode mudar o valor durante a conversa com o comando:

```text
/janela N        (N de 1 a 5)
```

O servidor envia `{"tipo": "JANELA", "janela": N}` e o cliente passa a usar o
novo valor **a partir do próximo lote**, porque o lote em andamento já foi
enviado. Valores fora de 1 a 5 são recusados nos dois lados. No modo
individual, a janela continua sendo 1.

A conexão guarda duas janelas separadas:

* `janela`: quantos pacotes o lado envia por lote (a que o servidor controla);
* `janela_recepcao`: quantos pacotes fora de ordem o destinatário SR aceita no
  buffer (fixa em 5, o tamanho do buffer).

Essa separação evita um problema: se o servidor reduzisse a própria janela de
recepção enquanto o cliente ainda tinha 5 pacotes a caminho, ele descartaria
pacotes válidos. É o mesmo princípio da janela de recepção do TCP: o receptor
tem um buffer fixo e anuncia ao remetente quanto ele pode enviar.

---

## 6. Máquinas de estados

### 6.1 Remetente

```text
              mensagem digitada
                     │
                     ▼
   ┌──────► [ENVIANDO LOTE] ── envia até `janela` pacotes, liga os temporizadores
   │                 │
   │                 ▼
   │         [AGUARDANDO CONFIRMAÇÕES] ◄─────────────────────────────┐
   │           │        │          │                                   │
   │          ACK      NACK      timeout                               │
   │           │        │          │                                   │
   │           ▼        ▼          ▼                                   │
   │       avança     reenvia:    reenvia:                             │
   │       a base     GBN → do    GBN → da base em diante              │
   │                  corrompido  SR  → só o pacote que expirou        │
   │                  em diante                                        │
   │                  SR → só ele                                      │
   │           │        └──────────┴───────────────────────────────────┘
   │           ▼
   │   lote todo confirmado?
   │     ├─ não → volta a [AGUARDANDO CONFIRMAÇÕES]
   └─────┴─ sim, ainda há pacotes → [ENVIANDO LOTE]
             sim, acabou → [ESPERANDO MENSAGEM]
```

### 6.2 Destinatário

```text
                    [AGUARDANDO PACOTE]
                            │
                       DATA recebido
                            │
               CRC-16 confere?
                 ├─ não → descarta, envia NACK ──────────────► volta
                 └─ sim → decifra
                            ├─ falhou → descarta, envia NACK ──► volta
                            └─ ok
                                 │
            ┌────────────────────┴────────────────────┐
           GBN                                        SR
            │                                          │
   seq == esperado?                        seq dentro da janela?
    ├─ sim → entrega, ACK(seq)               ├─ sim → guarda no buffer, ACK(seq),
    └─ não → descarta (duplicado ou            │        entrega tudo o que estiver em ordem
             fora de ordem),                   └─ seq < esperado → duplicado: reenvia ACK(seq)
             reenvia ACK do último em ordem
                                 │
               último pacote (fim = true) entregue?
                 └─ sim → exibe a mensagem completa
```

---

## 7. Manual de utilização

### 7.1 Requisitos

* Python 3;
* dois terminais abertos na pasta do projeto.

Não é necessário instalar nenhuma biblioteca externa.

### 7.2 Execução

Primeiro terminal (servidor):

```bash
python servidor.py
```

Segundo terminal (cliente):

```bash
python cliente.py
```

O cliente pede o modo (`individual` ou `lote`), o protocolo (`GBN` ou `SR`)
e o tamanho máximo do texto (mínimo de 30). Depois do handshake, os dois
lados podem conversar.

### 7.3 Enviando uma mensagem com falhas simuladas (cliente)

```text
[CLIENTE] Digite a mensagem (ou 'sair' para encerrar):
olá mundo, tudo bem?
[CLIENTE] Modo: em lote
[CLIENTE] Tamanho de cada pacote (1 a 4 caracteres):
4
[CLIENTE] Simulação de falhas: a mensagem terá 5 pacotes (índices 0 a 4).
[CLIENTE] Pacotes a PERDER (ex: 1,3 | Enter para nenhum):
2
[CLIENTE] Pacotes a CORROMPER (ex: 1,3 | Enter para nenhum):

[CLIENTE] ACKs a PERDER (ex: 1,3 | Enter para nenhum):

```

Para enviar sem falhas, basta apertar Enter nas três perguntas.

### 7.4 Comandos do servidor

* qualquer texto: envia uma mensagem ao cliente (sem simulação de falhas);
* `/janela N`: ajusta a janela de envio do cliente (N de 1 a 5);
* `sair`: encerra a conexão com o cliente atual;
* Ctrl+C: encerra o servidor.

### 7.5 Cores no terminal

* azul: pacotes enviados;
* amarelo: pacotes recebidos;
* vermelho: avisos (simulações, timeouts, descartes, NACK);
* verde: confirmações, ajustes de janela e mensagens completas.

---

## 8. Testes e demonstração

Todos os cenários abaixo foram executados com cliente e servidor reais, usando
a mensagem `olá mundo, tudo bem?` com pacotes de 4 caracteres (5 pacotes,
índices 0 a 4). Em todos eles, a mensagem completa foi exibida corretamente
no servidor.

| # | Modo / protocolo | Falha simulada | Comportamento observado |
|---|---|---|---|
| 1 | lote / GBN | perder o pacote 2 | o servidor descarta 3 e 4 como fora de ordem e repete o ACK do 1; no timeout o cliente reenvia **2, 3 e 4** |
| 2 | lote / SR | perder o pacote 2 | o servidor guarda 3 e 4 no buffer e confirma cada um; no timeout o cliente reenvia **só o 2** |
| 3 | lote / GBN | corromper o pacote 1 | o servidor detecta pelo CRC-16 e envia NACK; o cliente reenvia 1, 2, 3 e 4 na hora (2 ms) |
| 4 | lote / SR | corromper o pacote 1 | NACK; o cliente reenvia só o 1 |
| 5 | lote / SR | perder o ACK 4 | o cliente reenvia o 4 no timeout; o servidor identifica o **duplicado**, não entrega de novo e reconfirma |
| 6 | lote / GBN | perder o ACK 1 | **nenhuma retransmissão**: o ACK cumulativo do pacote 2 confirma o 1 |
| 7 | lote / GBN e SR | perder o 1 e corromper o 3 | o NACK resolve o 3 na hora e o timeout resolve o 1 |
| 8 | individual / GBN | perder o 1 e corromper o 3 | cada pacote é confirmado isoladamente; o 1 volta por timeout e o 3 por NACK |
| 9 | individual / SR | corromper o 2 e perder o ACK 4 | NACK para o 2; timeout e duplicado reconhecido para o 4 |
| 10 | lote / SR | servidor executa `/janela 2` entre duas mensagens | a primeira mensagem sai em um lote de 5; a segunda, em lotes de 2, 2 e 1 |
| 11 | lote / GBN | nenhuma | caminho sem erros, um lote de 5 |

### Exemplo: perda do pacote 2 no GBN (cenário 1)

```text
[CLIENTE] Enviando pacote seq=3179937357 payload="1c5cf2e054"
[CLIENTE] Enviando pacote seq=3179937358 payload="5d442f10"
[CLIENTE] Enviando pacote seq=3179937359 payload="5e6d541d"
[WARNING] [SIMULAÇÃO] Pacote seq=3179937359 perdido no canal (não foi entregue).
[CLIENTE] Enviando pacote seq=3179937360 payload="34100656"
[CLIENTE] Enviando pacote seq=3179937361 payload="160c1b56"
[CLIENTE] ACK recebido: ack=3179937357
[CLIENTE] ACK recebido: ack=3179937358
[CLIENTE] ACK recebido: ack=3179937358
[CLIENTE] ACK recebido: ack=3179937358
[WARNING] Pacote 3179937359 excedeu o tempo de envio. Reenviando...
[CLIENTE] Enviando pacote seq=3179937359 payload="5e6d541d"
[CLIENTE] Enviando pacote seq=3179937360 payload="34100656"
[CLIENTE] Enviando pacote seq=3179937361 payload="160c1b56"
[CLIENTE] ACK recebido: ack=3179937359
[CLIENTE] ACK recebido: ack=3179937360
[CLIENTE] ACK recebido: ack=3179937361
[SUCCESS] Lote enviado corretamente (ACK) time=1005ms
```

```text
[SERVIDOR] Pacote recebido: seq=3179937357 payload="olá "
[SERVIDOR] Pacote recebido: seq=3179937358 payload="mund"
[WARNING] Pacote seq=3179937360 fora de ordem. Descartado.
[WARNING] Pacote seq=3179937361 fora de ordem. Descartado.
[SERVIDOR] Pacote recebido: seq=3179937359 payload="o, t"
[SERVIDOR] Pacote recebido: seq=3179937360 payload="udo "
[SERVIDOR] Pacote recebido: seq=3179937361 payload="bem?"
[SERVIDOR] Mensagem completa: "olá mundo, tudo bem?"
```

### Exemplo: a mesma perda no SR (cenário 2)

```text
[WARNING] [SIMULAÇÃO] Pacote seq=2203490677 perdido no canal (não foi entregue).
[CLIENTE] ACK recebido: ack=2203490675
[CLIENTE] ACK recebido: ack=2203490676
[CLIENTE] ACK recebido: ack=2203490678
[CLIENTE] ACK recebido: ack=2203490679
[WARNING] Pacote 2203490677 excedeu o tempo de envio. Reenviando...
[CLIENTE] Enviando pacote seq=2203490677 payload="0b4d4411"
[CLIENTE] ACK recebido: ack=2203490677
[SUCCESS] Lote enviado corretamente (ACK) time=1007ms
```

A comparação entre os dois exemplos mostra a diferença central entre os
protocolos: com a mesma perda, o GBN reenvia três pacotes e o SR reenvia
apenas um.

### Exemplo: corrupção com NACK (cenário 4)

```text
[WARNING] [SIMULAÇÃO] Pacote seq=1022497698 corrompido no canal (payload "04030700" virou "14030700").
[CLIENTE] NACK recebido: nack=1022497698
[WARNING] Pacote 1022497698 chegou corrompido (NACK). Reenviando sem esperar o timeout...
[CLIENTE] Enviando pacote seq=1022497698 payload="04030700"
[SUCCESS] Lote enviado corretamente (ACK) time=1ms
```

```text
[WARNING] Pacote seq=1022497698 corrompido (checksum recebido=0x..., calculado=0x...). Descartado; enviando NACK.
```

### Exemplo: perda de ACK e duplicado (cenário 5)

```text
[WARNING] [SIMULAÇÃO] ACK ack=2627237310 perdido no canal (descartado pelo remetente).
[WARNING] Pacote 2627237310 excedeu o tempo de envio. Reenviando...
[SERVIDOR] Pacote recebido: seq=2627237310 payload="bem?"
[WARNING] Pacote seq=2627237310 duplicado (já entregue). Reenviando ACK.
```

> **Prints:** adicionar à pasta `imagens/` capturas de tela dos cenários 1, 2,
> 3, 5 e 10, nos dois terminais.

---

## 9. Evolução da implementação

| Etapa | Implementação |
|---|---|
| 1 | Cifra XOR com chave pré-compartilhada e deslocamento pelo `seq` (`aplicar_xor`). |
| 2 | Integração da cifra: cifrar → hexadecimal → checksum no envio; checksum → decifrar no recebimento. |
| 3 | Simulador de falhas no cliente: perda de pacote, corrupção de pacote e perda de ACK. |
| 4 | Diferenciação entre pacotes duplicados e fora de ordem no destinatário. |
| 5 | Segmento `NACK` e reenvio imediato de pacotes corrompidos. |
| 6 | Trava de impressão para evitar linhas misturadas entre threads. |
| 7 | Segmento `JANELA` e comando `/janela N` no servidor; janelas de envio e recepção separadas. |
| 8 | CRC-16/CCITT implementado à mão, substituindo o `zlib.crc32`. |

---

## 10. Processo de Construção e Uso de IA

### Estratégia de aprendizado com IA

Neste checkpoint, mudamos a forma de usar a IA. Pedimos explicitamente que
ela **não implementasse sozinha**, e sim explicasse o que estava acontecendo
para que pudéssemos apresentar e defender o código. Na prática:

* a IA leu o repositório e o enunciado e listou o que faltava (simulador,
  NACK, janela variável e os algoritmos da pontuação extra);
* nos algoritmos da pontuação extra, a IA foi usada **apenas para explicar o
  fundamento matemático**, como permite o enunciado: a divisão polinomial em
  módulo 2 do CRC (com um exemplo de 4 bits feito à mão) e a propriedade
  `(p ⊕ k) ⊕ k = p` do XOR;
* a IA desenhou as máquinas de estados do remetente e do destinatário
  (seção 6) a partir do código, e nós as usamos para conferir se cada
  caminho do código tinha um teste correspondente;
* nas partes de integração (simulador, NACK e janela), a IA auxiliou para implementar e
  explicou cada mudança; nós revisamos, rodamos os testes nas quatro
  combinações de modo e protocolo e preparamos a explicação para a arguição.

**Autoria dos algoritmos da pontuação extra:**

* **CRC-16 (`crc16`):** escrito por nós, linha por linha. A IA explicou o
  algoritmo em pseudocódigo, explicou os operadores de bits do Python e, a
  cada tentativa, apontou onde estava o erro sem fornecer a linha pronta.
  Quando pedimos que ela escrevesse a função, a IA recusou, explicando que
  isso faria o algoritmo deixar de ser hands-on. Depois que a função passou
  nos testes, a IA apenas a colou no arquivo e trocou o `zlib` por ela.
* **Cifra XOR (`aplicar_xor`):** a IA explicou a fórmula
  `c[i] = p[i] ⊕ k[(s+i) mod n]` e forneceu um esqueleto da função com três
  lacunas. Escolhemos a chave e tentamos preencher as lacunas; como travamos,
  a IA mostrou a tabela de correspondência entre a fórmula e as variáveis e,
  em seguida, completou as três lacunas com a explicação de cada uma. Nós
  testamos a função (cifrar e decifrar, deslocamentos diferentes, mensagem
  vazia e `seq` perto de 2³²) e a integramos ao envio (`montar_pacotes`).

### Análise crítica e debugging

**1. Bloco de decifrar no lugar errado (erro nosso, detectado pela IA).** Ao
integrar a cifra no recebimento, colocamos o `try` que decifra o pacote
**dentro** do `if checksum != ...`. Esse bloco só executa quando o pacote
chega corrompido; em um pacote íntegro, a variável `texto` nunca era criada e
o programa falharia. A IA identificou o problema ao ler o arquivo e moveu o
bloco para depois do `if`.

**2. Erros no CRC-16 (erros nossos, apontados pela IA sem dar a resposta).**
Durante a escrita da função cometemos quatro erros, todos corrigidos por nós
a partir das dicas:

* testar o bit com `& 8` em vez de `& 0x8000` (o `8` decimal testa o bit 3,
  não o bit 15);
* `for _ in (8)` sem o `range`;
* `registrador ^= (registrador << 1)`, que mistura o valor antigo com o
  deslocado, quando o certo é substituir (`=`) e depois fazer XOR com o
  gerador;
* o corte `registrador &= 0xFFFF` dentro do `else`. Esse foi o mais
  instrutivo: o CRC de `"123456789"` saía `0x129B1` em vez de `0x29B1`. Os 4
  últimos dígitos estavam certos, mas sobrava lixo acima do bit 15 sempre que
  o último bit passava pelo `if`. Um erro de indentação em Python muda a
  lógica do programa.

**3. Chave de 1 byte (erro nosso, detectado pela IA).** A primeira chave
escolhida foi `b"x"`. A IA mostrou que, com ela, `(deslocamento + i) % 1`
sempre dá 0: o deslocamento não teria efeito e a cifra teria só 256
possibilidades.

**4. Linhas misturadas no terminal (bug de concorrência).** Depois de
implementar o NACK, uma linha do log saiu assim:

```text
[WARNING] Pacote 1453424640 chegou corrompido (NACK). Reenviando sem esperar o timeout...[CLIENTE] ACK recebido: ack=1453424639
```

A thread de recepção e a thread de envio imprimiam ao mesmo tempo, e o
`print` não é atômico entre threads. A correção foi uma trava global de
impressão (`TRAVA_TELA`), usada em `log`, `aviso` e `sucesso`. É o mesmo
problema que, no checkpoint 2, nos fez usar uma trava para escrever no
socket.

**5. Erro de cálculo da IA na explicação do CRC.** Ao explicar o passo a
passo com o byte `0x31`, a IA afirmou que `0x19DFE ^ 0x1021` resultava em
`0x19DDF`. Ao conferir, o valor correto é `0x18DDF` (que, cortado para 16
bits, dá `0x8DDF`). A própria IA corrigiu na mensagem seguinte. Isso
reforçou a decisão de conferir cada valor no terminal em vez de confiar na
explicação.

**6. Log enganoso de "fora de ordem".** Ao testar a perda de ACK no GBN,
percebemos que um pacote duplicado (já entregue) aparecia como "fora de
ordem". A mensagem não estava errada a ponto de quebrar o protocolo, mas
confundiria a demonstração. O destinatário passou a diferenciar os dois
casos: `seq` menor que o esperado é duplicado, maior é fora de ordem.

**7. Janela de recepção (problema evitado no desenho).** Ao implementar o
`/janela N`, a primeira ideia era usar a mesma variável para a janela de
envio e a de recepção. Discutimos com a IA que, se o servidor reduzisse a
própria janela de recepção com pacotes ainda a caminho, o SR descartaria
pacotes válidos. Por isso as duas janelas foram separadas.

**8. Checksum com biblioteca não valeria a pontuação extra.** Ao ler o
enunciado da pontuação extra, a IA apontou que o checksum ainda usava o
`zlib.crc32`, o que não contaria como algoritmo "sem bibliotecas". Primeiro
decidimos manter o `zlib`; depois mudamos de ideia e implementamos o CRC-16.

### Prompts utilizados

1. Me auxilie para que eu consiga implementar esse último checkpoint, não
   implemente sozinho, quero entender como fazer e o que está acontecendo.
2. Não podemos esquecer que preciso garantir essa pontuação: *(trecho da
   pontuação extra do enunciado)*.
3. Vamos fazer XOR com chave, vá me guiando.
4. Vamos seguir com o NACK.
5. Garante o ponto extra? / As coisas que precisam ser implementadas para
    garantir os pontos extras foram implementadas?
6. Vamos fazer o CRC-16 agora. Vou fazer, mas
    preciso de mais ajuda sua.
7. Baseado nos outros 2 relatórios, faça esse último relatório.

### Decisões tomadas a partir das respostas da IA

**1. Levantamento do checkpoint 3.** A IA comparou o enunciado com o código e
mostrou que faltavam o simulador, o NACK (que não existia, embora o
reconhecimento negativo seja obrigatório) e a janela variável. Decidimos
implementar os três antes do relatório.

**2. Escolha da cifra.** Entre César, XOR com chave e AES-128, escolhemos o
XOR com chave: é simples de explicar, mais forte que a César e tem a
propriedade de a mesma função cifrar e decifrar.

**3. Ordem cifrar → checksum.** Decidimos calcular o checksum sobre o texto
cifrado, porque ele protege o que viaja no canal e permite descartar um
pacote corrompido antes de tentar decifrá-lo.

**4. Simulação por índice e uma única vez.** Decidimos que o usuário escolhe
os pacotes pelo índice na mensagem (e não pelo `seq` aleatório) e que cada
falha acontece só uma vez, para que a retransmissão demonstre a recuperação.

**5. NACK só para corrupção.** Decidimos que o NACK é enviado apenas quando o
pacote chega e falha na verificação. A perda continua sendo tratada pelo
temporizador, porque o destinatário não tem como saber de um pacote que não
chegou.

**6. Janela variável por comando do servidor.** Interpretamos o "vai variar de
1 a 5, determinado pelo servidor" como a possibilidade de o servidor mudar a
janela durante a conexão, e não só no handshake. A nova janela vale a partir
do próximo lote.

**7. CRC-16 hands-on.** Inicialmente decidimos manter o `zlib`, abrindo mão da
pontuação extra 1. Depois decidimos implementar o CRC-16 à mão e recusamos a
sugestão de deixar a IA escrever a função, para que o algoritmo fosse
realmente nosso.

---

## 11. Conclusão

Neste checkpoint, o protocolo passou a ser exercitado em um canal com falhas.
As perdas são recuperadas pelo temporizador, as corrupções são detectadas pelo
CRC-16 e recuperadas pelo NACK, os ACKs perdidos geram duplicados que o
destinatário reconhece, e a janela pode ser ajustada pelo servidor durante a
conexão. Os testes mostraram, com os mesmos erros, a diferença de
comportamento entre Go-Back-N e Repetição Seletiva.

Também implementamos à mão os dois algoritmos da pontuação extra: o CRC-16
para checagem de integridade e a cifra XOR para a troca de mensagens, sem
nenhuma biblioteca de checksum ou criptografia.

Com isso, a aplicação cobre todas as características do transporte confiável
pedidas no enunciado: soma de verificação, temporizador, número de sequência,
reconhecimento positivo e negativo, e janela com paralelismo.
