#recepcao, validacao e aprovacao
import socket
import json

HOST = "0.0.0.0" #todas as interfaces (nao so localhost)
PORT = 2000

JANELA_INICIAL = 5
TAMAN_MIN_TEXTO = 30 #texto

def enviar_msg(socket_conexao, mensagem):
    linha=json.dumps(mensagem, ensure_ascii=False, ) +'\n' #transforma no formato json
    socket_conexao.sendall(linha.encode("utf-8")) #converte a string em bytes
    #sendall : metodo que envia os bytes pela conexao (garante integridade)


def receber_msg(socket_conexao): 
    dados = b""

    while True:
        pedaco = socket_conexao.recv(1024)
        if not pedaco:
            raise ConnectionError("Conexão encerrada antes do esperado")


        dados += pedaco

        if b"\n" in dados:

            break

        linha, _, _ = dados.partition(b"\n")

        return json.loads(linha.decode("utf-8"))

    def main():

        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


        servidor.bind((HOST, PORT))

        servidor.listen(1)


        print(f"server aguardando conexão em {HOST}:{PORT}\n")

        try:
            conexao, endereco = servidor.accept()
            print(f"Cliente conectado: {endereco}")
            conexao.close()

        finally:

            servidor.close()

if __name__ == "__main__":
    main()

