(esses resumos dos commits ai foram feitos pelo gpt pra a proxima pessoa entender oq eu fiz)
commit 1
Neste commit, foi implementada a base da comunicação entre cliente e servidor utilizando sockets TCP. O servidor foi configurado para escutar na porta 2000 e aceitar conexões, enquanto o cliente foi preparado para se conectar ao servidor via `localhost`. Também foram criadas funções auxiliares para envio e recebimento de mensagens em JSON, utilizando `\n` como delimitador. Essa etapa estabelece a conexão básica que será utilizada posteriormente para implementar o handshake e o protocolo de comunicação da aplicação.




COMMIT 2
Neste commit, foi implementada e testada a comunicação inicial entre cliente e servidor utilizando sockets TCP. O cliente passou a estabelecer a conexão com o servidor e enviar uma mensagem de handshake estruturada em JSON, enquanto o servidor foi preparado para receber, decodificar e interpretar essa mensagem. Também foram corrigidos problemas de recebimento e estruturação das mensagens, estabelecendo a base necessária para a etapa de validação do handshake.

