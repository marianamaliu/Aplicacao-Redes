(esses resumos dos commits ai foram feitos pelo gpt pra a proxima pessoa entender oq eu fiz)
commit 1
Neste commit, foi implementada a base da comunicação entre cliente e servidor utilizando sockets TCP. O servidor foi configurado para escutar na porta 2000 e aceitar conexões, enquanto o cliente foi preparado para se conectar ao servidor via `localhost`. Também foram criadas funções auxiliares para envio e recebimento de mensagens em JSON, utilizando `\n` como delimitador. Essa etapa estabelece a conexão básica que será utilizada posteriormente para implementar o handshake e o protocolo de comunicação da aplicação.




COMMIT 2
Neste commit, foi implementada e testada a comunicação inicial entre cliente e servidor utilizando sockets TCP. O cliente passou a estabelecer a conexão com o servidor e enviar uma mensagem de handshake estruturada em JSON, enquanto o servidor foi preparado para receber, decodificar e interpretar essa mensagem. Também foram corrigidos problemas de recebimento e estruturação das mensagens, estabelecendo a base necessária para a etapa de validação do handshake.

COMMIT 3
Neste commit, foi implementada a etapa de validação e confirmação do handshake. O servidor passou a verificar os parâmetros recebidos do cliente, como modo de operação, protocolo, tamanho máximo do texto e tamanho da janela, identificando configurações válidas ou inválidas. Também foi implementada a resposta HANDSHAKE_ACK, permitindo ao servidor informar ao cliente se a configuração foi aceita ou rejeitada.


COMMIT 4
 Neste commit, foi ajustada a negociação da janela para que seu valor seja definido pelo servidor, utilizando a configuração inicial de 5, em vez de ser definido pelo cliente. Também foi atualizado o `HANDSHAKE_ACK` para retornar a janela determinada pelo servidor e mantida a confirmação dos parâmetros do handshake no cliente.