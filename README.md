
# Trabalho de Redes — Checkpoint 3

## Aplicação Cliente-Servidor com Transporte Confiável

Aplicação desenvolvida em **Python**, utilizando sockets TCP, com implementação de um protocolo de transporte confiável na camada de aplicação.

O projeto foi desenvolvido em três checkpoints:

- **Checkpoint 1:** conexão cliente-servidor e handshake de três vias.
- **Checkpoint 2:** troca de mensagens, fragmentação em pacotes, confirmações e implementação dos protocolos Go-Back-N (GBN) e Repetição Seletiva (SR).
- **Checkpoint 3:** simulação de erros e perdas, recuperação de pacotes, reconhecimento negativo (NACK), janela dinâmica, checksum CRC-16 e criptografia simétrica XOR.

Nesta última entrega, o objetivo é demonstrar que a aplicação consegue recuperar mensagens mesmo quando ocorrem perdas, corrupções ou falhas nas confirmações.

A documentação completa está disponível em `relatorio3.md`.

---

## 1. Requisitos

Para executar a aplicação, é necessário:

- Python 3 instalado;
- Dois terminais abertos na pasta do projeto;
- Acesso à porta TCP 2000.

Não é necessário instalar bibliotecas externas.

O projeto utiliza módulos da biblioteca padrão do Python.

---

## 2. Arquivos principais

| Arquivo | Descrição |
|---|---|
| `servidor.py` | Inicializa o servidor, aceita conexões e permite alterar a janela de transmissão. |
| `cliente.py` | Inicializa o cliente, solicita os parâmetros e permite configurar as falhas simuladas. |
| `protocolo.py` | Implementa o protocolo, CRC-16, XOR, ACK, NACK, timeout, retransmissões, GBN e SR. |
| `padrao_msgs.txt` | Contém o padrão das mensagens exibidas no terminal. |
| `relatorio3.md` | Relatório completo do Checkpoint 3, incluindo especificação, testes, resultados e documentação do uso de IA. |
| `imagens/` | Contém as evidências dos testes realizados. |

---

## 3. Como executar

### 3.1. Iniciar o servidor

Abra um terminal na pasta do projeto e execute:

```bash
python servidor.py
```

O servidor ficará aguardando conexões na porta 2000.

Mantenha esse terminal aberto durante os testes.

### 3.2. Iniciar o cliente

Abra um segundo terminal na mesma pasta e execute:

```bash
python cliente.py
```

O cliente solicitará os parâmetros iniciais:

```text
Configuração da conexão

Modo de operação (individual/lote): lote
Protocolo (GBN/SR): SR
Tamanho máximo do texto: 100
```

Após a configuração, será realizado o handshake de três vias:

1. Cliente envia SYN.
2. Servidor responde SYN-ACK.
3. Cliente confirma com ACK.

A conexão será estabelecida com janela inicial de tamanho 5.

---

## 4. Enviando mensagens

Após o handshake, o cliente solicitará uma mensagem:

```text
[CLIENTE] Digite a mensagem (ou 'sair' para encerrar):
```

Digite, por exemplo:

```text
olá mundo, tudo bem?
```

Em seguida, informe o tamanho dos pacotes:

```text
[CLIENTE] Modo: em lote
[CLIENTE] Tamanho de cada pacote (1 a 4 caracteres):
4
```

A mensagem será dividida em cinco pacotes:

```text
Pacote 0: "olá "
Pacote 1: "mund"
Pacote 2: "o, t"
Pacote 3: "udo "
Pacote 4: "bem?"
```

Cada pacote recebe um número de sequência e um checksum.

O conteúdo é cifrado com XOR antes de ser transmitido.

O servidor verifica a integridade, decifra os pacotes e reconstrói a mensagem original.

Ao final, deverá apresentar:

```text
[SERVIDOR] Mensagem completa: "olá mundo, tudo bem?"
```

Os números de sequência são gerados dinamicamente e podem variar entre as execuções.

---

## 5. Simulador de erros e perdas

O Checkpoint 3 implementa um simulador determinístico de falhas na camada de aplicação.

Após informar a mensagem e o tamanho dos pacotes, o cliente solicita:

```text
[CLIENTE] Simulação de falhas: a mensagem terá 5 pacotes (índices 0 a 4).

[CLIENTE] Pacotes a PERDER (ex: 1,3 | Enter para nenhum):

[CLIENTE] Pacotes a CORROMPER (ex: 1,3 | Enter para nenhum):

[CLIENTE] ACKs a PERDER (ex: 1,3 | Enter para nenhum):
```

O usuário pode configurar três tipos de falhas:

| Falha | Funcionamento | Recuperação |
|---|---|---|
| Perda de pacote | O pacote não é entregue ao destinatário. | Timeout e retransmissão. |
| Corrupção de pacote | O conteúdo do pacote é alterado durante a simulação. | Detecção pelo CRC-16, NACK e retransmissão. |
| Perda de ACK | Uma confirmação é descartada pelo remetente. | ACK cumulativo ou timeout, dependendo do protocolo. |

Cada falha configurada é aplicada uma única vez, permitindo que a retransmissão ocorra normalmente.

### 5.1. Exemplo: perda de pacote

Utilize:

```text
Modo: lote
Protocolo: GBN
Mensagem: olá mundo, tudo bem?
Tamanho do pacote: 4

Pacotes a PERDER: 2
Pacotes a CORROMPER:
ACKs a PERDER:
```

Nesse teste:

1. O pacote de índice 2 é perdido.
2. O servidor GBN descarta os pacotes 3 e 4 por estarem fora de ordem.
3. O temporizador do cliente expira.
4. O cliente retransmite os pacotes 2, 3 e 4.
5. O servidor reconstrói a mensagem corretamente.

### 5.2. Exemplo: corrupção de pacote

Utilize:

```text
Modo: lote
Protocolo: SR
Mensagem: olá mundo, tudo bem?
Tamanho do pacote: 4

Pacotes a PERDER:
Pacotes a CORROMPER: 1
ACKs a PERDER:
```

Nesse teste:

1. O pacote de índice 1 é enviado com o conteúdo alterado.
2. O servidor detecta a corrupção pelo CRC-16.
3. O servidor descarta o pacote e envia um NACK.
4. O cliente retransmite somente o pacote 1.
5. A mensagem é reconstruída corretamente.

### 5.3. Exemplo: perda de ACK

Utilize:

```text
Modo: lote
Protocolo: SR
Mensagem: olá mundo, tudo bem?
Tamanho do pacote: 4

Pacotes a PERDER:
Pacotes a CORROMPER:
ACKs a PERDER: 4
```

Nesse teste:

1. O servidor recebe normalmente o pacote 4.
2. O ACK correspondente é descartado pelo cliente.
3. O temporizador expira.
4. O cliente retransmite o pacote 4.
5. O servidor identifica o pacote duplicado e reenvia o ACK.

A mensagem não é entregue duas vezes.

### 5.4. Envio sem falhas

Para enviar uma mensagem normalmente, pressione Enter nas três perguntas de simulação.

---

## 6. Protocolos GBN e SR

A aplicação permite selecionar dois protocolos de transmissão confiável.

### Go-Back-N (GBN)

No GBN:

- O destinatário aceita pacotes na ordem esperada.
- Pacotes recebidos fora de ordem são descartados.
- Os ACKs são cumulativos.
- Quando ocorre uma perda, o remetente retransmite os pacotes pendentes a partir do pacote perdido.

### Repetição Seletiva (SR)

No SR:

- O destinatário pode armazenar pacotes recebidos fora de ordem.
- Cada pacote possui confirmação individual.
- O remetente retransmite somente os pacotes que precisam ser recuperados.
- Pacotes duplicados são identificados e não são entregues novamente.

A principal diferença é que o SR evita retransmissões desnecessárias de pacotes já recebidos corretamente.

---

## 7. Janela dinâmica

A janela de transmissão possui valor inicial de 5 e pode ser alterada pelo servidor para qualquer valor entre 1 e 5.

Para alterar a janela, digite no terminal do servidor:

```text
/janela 2
```

O servidor enviará uma mensagem de controle ao cliente.

O cliente receberá a atualização e utilizará o novo tamanho a partir do próximo lote.

### Exemplo

Com janela de tamanho 5, uma mensagem contendo cinco pacotes pode ser transmitida em um único lote:

```text
Janela = 5

Lote 1: [0, 1, 2, 3, 4]
```

Após executar `/janela 2`, uma nova mensagem de cinco pacotes será enviada em três lotes:

```text
Janela = 2

Lote 1: [0, 1]
Lote 2: [2, 3]
Lote 3: [4]
```

Cada lote é confirmado antes do envio do próximo.

No modo individual, os pacotes continuam sendo enviados isoladamente.

---

## 8. CRC-16 — Verificação de integridade

O projeto utiliza um algoritmo CRC-16/CCITT implementado manualmente em `protocolo.py`.

O algoritmo:

1. Recebe os dados cifrados.
2. Calcula o checksum utilizando operações binárias.
3. Inclui o checksum no pacote.
4. Permite ao destinatário verificar a integridade dos dados recebidos.

Caso o checksum calculado seja diferente do recebido, o pacote é descartado e um NACK é enviado.

A implementação utiliza:

```text
Polinômio: 0x1021
Valor inicial: 0xFFFF
```

O algoritmo não utiliza bibliotecas externas para calcular o checksum.

---

## 9. Criptografia simétrica XOR

A aplicação utiliza uma cifra simétrica baseada na operação XOR, implementada em `protocolo.py`.

Antes do envio:

1. O texto é convertido para bytes.
2. Os bytes são combinados com uma chave por meio de XOR.
3. O resultado é convertido para hexadecimal.
4. O conteúdo cifrado é enviado com seu checksum.

No recebimento, o destinatário aplica novamente o XOR para recuperar a mensagem original.

A propriedade utilizada é:

```text
(p XOR k) XOR k = p
```

A mesma função é utilizada para cifrar e decifrar.

Essa implementação tem finalidade acadêmica e não substitui algoritmos criptográficos modernos em aplicações reais.

---

## 10. Testes realizados

O Checkpoint 3 contempla testes de funcionamento normal e recuperação de falhas.

| Cenário | Protocolo | Teste |
|---|---|---|
| 1 | GBN | Perda do pacote 2 |
| 2 | SR | Perda do pacote 2 |
| 3 | GBN | Corrupção do pacote 1 |
| 4 | SR | Corrupção do pacote 1 |
| 5 | SR | Perda do ACK 4 |
| 6 | GBN | Perda do ACK 1 |
| 7 | GBN e SR | Perda e corrupção simultâneas |
| 8 | GBN individual | Perda e corrupção |
| 9 | SR individual | Corrupção e perda de ACK |
| 10 | SR | Alteração dinâmica da janela |
| 11 | GBN | Transmissão sem falhas |

Os testes demonstram:

- Detecção de pacotes corrompidos;
- Recuperação de pacotes perdidos;
- Tratamento de ACKs perdidos;
- Identificação de pacotes duplicados;
- Retransmissões por timeout;
- Retransmissões por NACK;
- Diferenças entre GBN e SR;
- Alteração dinâmica da janela;
- Reconstrução correta das mensagens.

As evidências e os registros das execuções estão documentados na **Seção 8 do `relatorio3.md`**.

---

## 11. Configurações aceitas

| Parâmetro | Valores |
|---|---|
| Modo de operação | `individual` ou `lote` |
| Protocolo | `GBN` ou `SR` |
| Tamanho máximo do texto | Mínimo de 30 caracteres |
| Payload por pacote | 1 a 4 caracteres |
| Janela de transmissão | 1 a 5 |
| Janela inicial | 5 |
| Timeout | 1 segundo |
| Endereço padrão do servidor | `0.0.0.0` |
| Porta padrão | `2000` |

---

## 12. Comandos do servidor

O terminal do servidor aceita:

| Comando | Função |
|---|---|
| `/janela N` | Altera a janela do cliente para N, entre 1 e 5. |
| `sair` | Encerra a conexão com o cliente atual. |
| `Ctrl+C` | Encerra o servidor. |
| Texto comum | Envia uma mensagem ao cliente. |

---

## 13. Encerrando a conexão

Para encerrar a comunicação, digite:

```text
sair
```

A aplicação utiliza mensagens FIN e FIN-ACK para finalizar a conexão.

Após a desconexão, o servidor permanece disponível para aceitar novos clientes.

Para interromper completamente o servidor, pressione `Ctrl+C`.

---

## 14. Cores no terminal

As mensagens utilizam cores para facilitar a visualização:

- **Azul:** pacotes enviados.
- **Amarelo:** pacotes recebidos.
- **Vermelho:** avisos, perdas, corrupções, timeouts e retransmissões.
- **Verde:** confirmações, alterações de janela e mensagens completas.

No Windows, recomenda-se utilizar PowerShell ou Windows Terminal.

---

## 15. Documentação completa

Para consultar a especificação detalhada do protocolo, as máquinas de estados, a implementação dos algoritmos, os testes e o processo de construção com IA, consulte:

**`relatorio3.md`**

O relatório contém a documentação técnica completa da entrega final.

---

## 16. Conclusão

O Checkpoint 3 completa a implementação do protocolo de transporte confiável na camada de aplicação.

O sistema permite simular erros e perdas, detectar corrupções, recuperar pacotes, tratar confirmações perdidas e controlar dinamicamente a janela de transmissão.

Além disso, utiliza CRC-16 para verificação de integridade e XOR para cifrar e decifrar as mensagens.

Com isso, a aplicação demonstra os mecanismos de transporte confiável solicitados no Trabalho I de Redes.
