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

def validar_handshake(mensagem):
    if mensagem.get("tipo") != "HANDSHAKE":
        return False, "Tipo de mensagem invalido"

    if mensagem.get("modo") not in ["lote", "individual"]:
        return False, "Modo de operação invalido"

    if mensagem.get("protocolo") not in ["GBN", "SR"]:
        return False, "Protocolo invalido"

    if mensagem.get("max_texto", 0) < TAMAN_MIN_TEXTO:
        return False, f"tamanho minimo do texto é {TAMAN_MIN_TEXTO}"

    return True, "Handshake valido"
def main():

        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


        servidor.bind((HOST, PORT))

        servidor.listen(1)


        print(f"server aguardando conexão em {HOST}:{PORT}\n")

        try:
            conexao, endereco = servidor.accept()
            print(f"Cliente conectado: {endereco}")


            mensagem = receber_msg(conexao)
            print("Mensagem recebida:")

            print(mensagem)

            valido, motivo = validar_handshake(mensagem)

            if valido:
                print("Handshake valida")

                resposta = {
                    "tipo": "HANDSHAKE_ACK", "status": "OK", "modo": mensagem["modo"], "protocolo": mensagem["protocolo"], "max_texto": mensagem["max_texto"], "janela": JANELA_INICIAL


                }

            else:
                print(f"Handshake invalido: {motivo}")
                resposta = {
                    "tipo": "HANDSHAKE_ACK",
                    "status": "ERRO",
                    "motivo": motivo
                }

            enviar_msg(conexao, resposta)

            print("resposta enviada ao cliente")


            conexao.close()

        finally:

            servidor.close()

if __name__ == "__main__":
    main()

