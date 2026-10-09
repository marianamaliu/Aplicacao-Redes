# Aplicacao-Redes
Handshake precisou ser atualizado, pois não seguia o padrão de SYN, SEQ e ACK os 
quais permitem a validação do handshake

## Handshake de três vias

O cliente e o servidor estabelecem os parâmetros iniciais em três segmentos JSON,
delimitados por `\n`, sem iniciar a troca de mensagens de dados:

1. **SYN — cliente → servidor:** `syn: 1`, `seq: client_isn` e `ack: 0`, junto
   dos parâmetros solicitados (`modo`, `protocolo` e `max_texto`).
2. **SYN-ACK — servidor → cliente:** `syn: 1`, `seq: server_isn` e
   `ack: client_isn + 1`. Se os parâmetros forem aceitos, a resposta inclui
   `status: "OK"` e os valores negociados.
3. **ACK — cliente → servidor:** `syn: 0`, `seq: client_isn + 1` e
   `ack: server_isn + 1`. O servidor valida os dois números antes de considerar
   o handshake concluído.

Os números de sequência iniciais são aleatórios de 32 bits; o incremento é
circular. Após o ACK final, a conexão é encerrada. O envio de mensagens de dados
fica para uma etapa posterior.

