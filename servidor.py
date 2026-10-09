#recepcao, validacao e aprovacao
import socket
import json
import secrets

HOST = "0.0.0.0" #todas as interfaces (nao so localhost)
PORT = 2000
JANELA_INICIAL = 5
TAMAN_MIN_TEXTO = 30 #texto
LIMITE_SEQ = 1 << 32


def proximo_seq(numero):
    return (numero + 1) % LIMITE_SEQ


def enviar_msg(socket_conexao, mensagem):
    linha=json.dumps(mensagem, ensure_ascii=False, ) +'\n' #transforma no formato json
    socket_conexao.sendall(linha.encode("utf-8")) #converte a string em bytes
    


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


def validar_syn(mensagem):
    
    if mensagem.get("tipo") != "SYN" or type(mensagem.get("syn")) is not int or mensagem["syn"] != 1:
        return False, "Segmento SYN invalido"

    client_isn = mensagem.get("seq")
    if type(client_isn) is not int or not 0 <= client_isn < LIMITE_SEQ:
        return False, "Número de sequência do cliente invalido"

    if type(mensagem.get("ack")) is not int or mensagem["ack"] != 0:
        return False, "Campo ACK do segmento SYN deve ser zero"

    if mensagem.get("protocolo") not in ["GBN", "SR"]:
        return False, "Protocolo invalido"

    max_texto = mensagem.get("max_texto")
    if type(max_texto) is not int or max_texto < TAMAN_MIN_TEXTO:
        return False, f"tamanho minimo do texto é {TAMAN_MIN_TEXTO}"

    return True, "Handshake valido"


def validar_ack(mensagem, client_isn, server_isn):
    if not isinstance(mensagem, dict):
        return False, "Segmento recebido não é um objeto JSON"

    if mensagem.get("tipo") != "ACK" or type(mensagem.get("syn")) is not int or mensagem["syn"] != 0:
        return False, "Segmento ACK invalido"

    seq = mensagem.get("seq")
    ack = mensagem.get("ack")
    if type(seq) is not int or seq != proximo_seq(client_isn):
        return False, "Número de sequência do ACK do cliente invalido"
    if type(ack) is not int or ack != proximo_seq(server_isn):
        return False, "Número ACK do cliente invalido"

    return True, "Handshake concluido"


def main():

        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind((HOST, PORT))

        servidor.listen(1)


        print(f"server aguardando conexão em {HOST}:{PORT}\n")

        try:
            conexao, endereco = servidor.accept()
            print(f"Cliente conectado: {endereco}")


            syn = receber_msg(conexao)
            print("SYN recebido:")
            print(syn)

            valido, motivo = validar_syn(syn)

            if valido:
                client_isn = syn["seq"]
                server_isn = secrets.randbits(32)

                syn_ack = {
                    "tipo": "SYN_ACK",
                    "syn": 1,
                    "seq": server_isn,
                    "ack": proximo_seq(client_isn),
                    "status": "OK",
                    "modo": syn["modo"],
                    "protocolo": syn["protocolo"],
                    "max_texto": syn["max_texto"],
                    "janela": JANELA_INICIAL,
                }
            else:
                print(f"SYN invalido: {motivo}")
                syn_ack = {
                    "tipo": "SYN_ACK",
                    "syn": 1,
                    "status": "ERRO",
                    "motivo": motivo
                }

            enviar_msg(conexao, syn_ack)
            print("SYN-ACK enviado")

            if valido:
                ack = receber_msg(conexao)
                print("ACK recebido:")
                print(ack)

                ack_valido, motivo = validar_ack(ack, client_isn, server_isn)
                if ack_valido:
                    print("Handshake de três vias concluído; aguardando a próxima etapa, sem troca de dados.")
                else:
                    print(f"Handshake não concluído: {motivo}")

            conexao.close()
        finally:

            servidor.close()

if __name__ == "__main__":
    main()
