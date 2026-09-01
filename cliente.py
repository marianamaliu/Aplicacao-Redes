import socket
import json

HOST = "127.0.0.1"
PORT = 2000

def enviar_msg(socket_conexao, mensagem): #criando handshake
    linha = json.dumps(mensagem, ensure_ascii = False) + '\n'
    socket_conexao.sendall(linha.encode("utf-8"))


def receber_msg(socket_conexao):
    dados = b""
    while True:

        pedaco = socket_conexao.recv(1024)
        if not pedaco:
            raise ConnectionError("Conexão encerrada")


        dados += pedaco
        if b"\n" in dados:
            break

    linha, _, _ = dados.partition(b"\n")


    return json.loads(linha.decode("utf-8"))

def main():
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cliente.connect((HOST, PORT))
    try:
        print(f"conectado ao server {HOST}:{PORT}")
        handshake = {"tipo": "HANDSHAKE", "modo": "lote", "protocolo": "GBN", "max_texto": 100, "janela": 5}
        enviar_msg(cliente, handshake)

        print("Handshake enviado")

        resposta = receber_msg(cliente)
        print("Resposta do server: ", resposta)

    except ConnectionRefusedError:
            print("Não foi possível conectar ao servidor.")
        

    finally:
            cliente.close()


if __name__ == "__main__":
    main()
