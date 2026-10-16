# recepcao, validacao e aprovacao
import socket
import json
import secrets
import zlib
import os

HOST = "0.0.0.0"  # todas as interfaces (nao so localhost)
PORT = 2000
JANELA_INICIAL = 5
TAMAN_MIN_TEXTO = 30 #texto
LIMITE_SEQ = 1 << 32
MODOS = ["individual", "lote"]
PROTOCOLOS = ["GBN", "SR"]

AMARELO = "\033[93m"
VERMELHO = "\033[91m"
VERDE = "\033[92m"
RESET = "\033[0m"


def colorir(texto, cor):
    return f"{cor}{texto}{RESET}"


class LeitorMensagens:
    def __init__(self, socket_conexao):
        self.socket = socket_conexao
        self.buffer = b""

    def ler_linha(self):
        while b"\n" not in self.buffer:
            dados = self.socket.recv(4096)
            if not dados:
                raise ConnectionError("Conexão encerrada antes do esperado")
            self.buffer += dados
        linha, _, self.buffer = self.buffer.partition(b"\n")
        return linha.decode("utf-8")


def eh_inteiro(valor):
    return type(valor) is int


def proximo_seq(numero):
    return (numero + 1) % LIMITE_SEQ


def enviar_msg(socket_conexao, mensagem):
    linha = json.dumps(mensagem, ensure_ascii=False) + "\n"  # transforma no formato json
    socket_conexao.sendall(linha.encode("utf-8"))  # converte a string em bytes


def receber_msg(leitor):
    mensagem = json.loads(leitor.ler_linha())
    if not isinstance(mensagem, dict):
        raise ValueError("Mensagem recebida não é um objeto JSON")
    return mensagem


def validar_syn(mensagem):
    if mensagem.get("tipo") != "SYN" or not eh_inteiro(mensagem.get("syn")) or mensagem["syn"] != 1:
        return False, "Segmento SYN invalido"

    client_isn = mensagem.get("seq")
    if not eh_inteiro(client_isn) or not 0 <= client_isn < LIMITE_SEQ:
        return False, "Número de sequência do cliente invalido"

    if not eh_inteiro(mensagem.get("ack")) or mensagem["ack"] != 0:
        return False, "Campo ACK do segmento SYN deve ser zero"

    if mensagem.get("modo") not in MODOS:
        return False, f"Modo invalido (aceitos: {', '.join(MODOS)})"

    if mensagem.get("protocolo") not in PROTOCOLOS:
        return False, f"Protocolo invalido (aceitos: {', '.join(PROTOCOLOS)})"

    max_texto = mensagem.get("max_texto")
    if not eh_inteiro(max_texto) or max_texto < TAMAN_MIN_TEXTO:
        return False, f"tamanho minimo do texto é {TAMAN_MIN_TEXTO}"

    return True, "Handshake valido"


def validar_ack(mensagem, client_isn, server_isn):
    if mensagem.get("tipo") != "ACK" or not eh_inteiro(mensagem.get("syn")) or mensagem["syn"] != 0:
        return False, "Segmento ACK invalido"

    seq = mensagem.get("seq")
    ack = mensagem.get("ack")
    if not eh_inteiro(seq) or seq != proximo_seq(client_isn):
        return False, "Número de sequência do ACK do cliente invalido"
    if not eh_inteiro(ack) or ack != proximo_seq(server_isn):
        return False, "Número ACK do cliente invalido"

    return True, "Handshake concluido"


def imprimir_json(mensagem):
    print(json.dumps(mensagem, indent=4, ensure_ascii=False))


def realizar_handshake(conexao, leitor):
    syn = receber_msg(leitor)
    print("SYN recebido:")
    imprimir_json(syn)

    valido, motivo = validar_syn(syn)
    if not valido:
        print(f"SYN invalido: {motivo}")
        enviar_msg(conexao, {
            "tipo": "SYN_ACK",
            "syn": 1,
            "status": "ERRO",
            "motivo": motivo,
        })
        print("SYN-ACK de erro enviado")
        return None

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
    enviar_msg(conexao, syn_ack)
    print("SYN-ACK enviado")

    ack = receber_msg(leitor)
    print("ACK recebido:")
    print(ack)

    ack_valido, motivo = validar_ack(ack, client_isn, server_isn)
    if not ack_valido:
        print(f"Handshake não concluído: {motivo}")
        return None

    print("Handshake de três vias concluído; aguardando a próxima etapa, sem troca de dados.")

    return {
        "seq_esperado": proximo_seq(client_isn),
        "seq_servidor": proximo_seq(server_isn),
        "modo": syn["modo"],
        "protocolo": syn["protocolo"],
        "max_texto": syn["max_texto"],
        "janela": JANELA_INICIAL,
    }


def calcular_checksum(payload):
    return zlib.crc32(payload.encode("utf-8"))


def pacote_valido(mensagem):
    return (
        eh_inteiro(mensagem.get("seq"))
        and isinstance(mensagem.get("payload"), str)
        and eh_inteiro(mensagem.get("checksum"))
    )


def enviar_ack(conexao, seq):
    enviar_msg(conexao, {"tipo": "ACK", "ack": seq})


def receber_dados(conexao, leitor, sessao):
    seq_base = sessao["seq_esperado"]
    protocolo = sessao["protocolo"]
    modo = sessao["modo"]
    janela = sessao["janela"] if modo == "lote" else 1

    esperado = 0
    partes = []
    fora_de_ordem = {}
    print()

    while True:
        mensagem = receber_msg(leitor)
        tipo = mensagem.get("tipo")

        if tipo == "FIN":
            seq_fin = (seq_base + esperado) % LIMITE_SEQ
            if mensagem.get("seq") != seq_fin:
                print(colorir(f"[WARNING] FIN com seq inesperado ({mensagem.get('seq')}). Ignorado.", VERMELHO))
                continue
            enviar_msg(conexao, {"tipo": "FIN_ACK", "ack": proximo_seq(seq_fin)})
            mensagem_completa = "".join(partes)
            print(colorir(f'[SERVIDOR] Mensagem completa: "{mensagem_completa}"', VERDE))
            print("[SERVIDOR] FIN recebido e confirmado; conexão encerrada.")
            return mensagem_completa

        if tipo != "DATA" or not pacote_valido(mensagem):
            print(colorir("[WARNING] Mensagem fora do formato esperado. Ignorada.", VERMELHO))
            continue

        seq = mensagem["seq"]
        payload = mensagem["payload"]
        indice = (seq - seq_base) % LIMITE_SEQ
        checksum = calcular_checksum(payload)

        if checksum != mensagem["checksum"]:
            print(colorir(
                f"[WARNING] Pacote seq={seq} corrompido "
                f"(checksum recebido=0x{mensagem['checksum']:08X}, calculado=0x{checksum:08X}). Descartado.",
                VERMELHO,
            ))
            if protocolo == "GBN" and esperado > 0:
                enviar_ack(conexao, (seq_base + esperado - 1) % LIMITE_SEQ)
            continue

        if modo == "lote":
            print(colorir(f'[SERVIDOR] Pacote recebido: seq={seq} checksum=0x{checksum:08X} payload="{payload}"', AMARELO))
        else:
            print(colorir(f"[SERVIDOR] Pacote recebido: seq={seq} checksum=0x{checksum:08X}", AMARELO))

        if protocolo == "GBN":
            if indice == esperado:
                partes.append(payload)
                esperado += 1
            else:
                print(colorir(f"[WARNING] Pacote seq={seq} fora de ordem. Descartado.", VERMELHO))
            if esperado > 0:
                enviar_ack(conexao, (seq_base + esperado - 1) % LIMITE_SEQ)
        else:
            if esperado <= indice < esperado + janela:
                fora_de_ordem[indice] = payload
                enviar_ack(conexao, seq)
                while esperado in fora_de_ordem:
                    partes.append(fora_de_ordem.pop(esperado))
                    esperado += 1
            elif indice < esperado:
                enviar_ack(conexao, seq)


def main():
    os.system("")  # habilita cores no terminal do Windows

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PORT))
    servidor.listen(1)

    print(f"server aguardando conexão em {HOST}:{PORT}\n")

    try:
        conexao, endereco = servidor.accept()
        conexao.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"Cliente conectado: {endereco}")
        leitor = LeitorMensagens(conexao)

        try:
            sessao = realizar_handshake(conexao, leitor)
            if sessao is not None:
                receber_dados(conexao, leitor, sessao)
        except (ConnectionError, ValueError) as erro:
            print(f"Falha na comunicação: {erro}")
        finally:
            conexao.close()
    finally:
        servidor.close()


if __name__ == "__main__":
    main()