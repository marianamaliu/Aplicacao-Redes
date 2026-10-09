import socket
import json
import secrets

HOST = "127.0.0.1"
PORT = 2000
LIMITE_SEQ = 1 << 32


def proximo_seq(numero):
    return (numero + 1) % LIMITE_SEQ


def enviar_msg(socket_conexao, mensagem):
    linha = json.dumps(mensagem, ensure_ascii=False) + "\n"
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

    try:
        cliente.connect((HOST, PORT))
        print(f"Conectado ao servidor {HOST}:{PORT}")

        client_isn = secrets.randbits(32)
        syn = {
            "tipo": "SYN",
            "syn": 1,
            "seq": client_isn,
            "ack": 0,
            "modo": "lote",
            "protocolo": "GBN",
            "max_texto": 100,
        }
        enviar_msg(cliente, syn)
        print(f"SYN enviado (seq={client_isn})")

        syn_ack = receber_msg(cliente)
                
        if syn_ack.get("status") != "OK":
            print("Handshake rejeitado pelo servidor.")
            print(f"Motivo: {syn_ack.get('motivo', 'motivo não informado')}")
            return
        server_isn = syn_ack.get("seq")

        ack = {
            "tipo": "ACK",
            "syn": 0,
            "seq": proximo_seq(client_isn),
            "ack": proximo_seq(server_isn),
        }
        enviar_msg(cliente, ack)
        print(f"ACK enviado (seq={ack['seq']}, ack={ack['ack']})")
        print("Handshake de três vias concluído; nenhuma mensagem de dados foi enviada.")

        print(f"Modo: {syn_ack['modo']}")
        print(f"Protocolo: {syn_ack['protocolo']}")
        print(f"Tamanho máximo do texto: {syn_ack['max_texto']}")
        print(f"Tamanho da janela: {syn_ack['janela']}")

    except ConnectionRefusedError:
        print("Não foi possível conectar ao servidor.")
    except (ConnectionError, ValueError) as erro:
        print(f"Falha no handshake: {erro}")
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
