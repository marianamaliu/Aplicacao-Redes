import socket
import json
import secrets
import time
import zlib
import os

HOST = "127.0.0.1"
PORT = 2000
LIMITE_SEQ = 1 << 32
MODOS = ["individual", "lote"]
PROTOCOLOS = ["GBN", "SR"]
NOMES_MODO = {"individual": "isolado", "lote": "em lote"}
TIMEOUT = 1.0
TENTATIVAS_FIN = 5

AZUL = "\033[94m"
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
                raise ConnectionError("Conexão encerrada pelo servidor")
            self.buffer += dados
        linha, _, self.buffer = self.buffer.partition(b"\n")
        return linha.decode("utf-8")


def eh_inteiro(valor):
    return type(valor) is int


def proximo_seq(numero):
    return (numero + 1) % LIMITE_SEQ


def enviar_msg(socket_conexao, mensagem):
    linha = json.dumps(mensagem, ensure_ascii=False) + "\n"
    socket_conexao.sendall(linha.encode("utf-8"))


def receber_msg(leitor):
    mensagem = json.loads(leitor.ler_linha())
    if not isinstance(mensagem, dict):
        raise ValueError("Mensagem recebida não é um objeto JSON")
    return mensagem


def escolher_opcao(pergunta, opcoes):
    while True:
        resposta = input(f"{pergunta} ({'/'.join(opcoes)}): ").strip()
        for opcao in opcoes:
            if resposta.lower() == opcao.lower():
                return opcao
        print(f"Opção inválida. Escolha entre: {', '.join(opcoes)}")


def escolher_inteiro(pergunta):
    while True:
        resposta = input(f"{pergunta}: ").strip()
        if resposta.isdigit():
            return int(resposta)
        print("Digite um número inteiro positivo.")


def validar_syn_ack(mensagem, client_isn, syn):
    if mensagem.get("tipo") != "SYN_ACK" or not eh_inteiro(mensagem.get("syn")) or mensagem["syn"] != 1:
        return False, "Segmento SYN-ACK inválido"

    if mensagem.get("status") != "OK":
        return False, mensagem.get("motivo", "motivo não informado")

    server_isn = mensagem.get("seq")
    if not eh_inteiro(server_isn) or not 0 <= server_isn < LIMITE_SEQ:
        return False, "Número de sequência do servidor inválido"

    if not eh_inteiro(mensagem.get("ack")) or mensagem["ack"] != proximo_seq(client_isn):
        return False, "Número ACK do servidor inválido"

    for campo in ["modo", "protocolo", "max_texto"]:
        if mensagem.get(campo) != syn[campo]:
            return False, f"Servidor respondeu com '{campo}' diferente do solicitado"

    janela = mensagem.get("janela")
    if not eh_inteiro(janela) or janela < 1:
        return False, "Tamanho de janela inválido"

    return True, "SYN-ACK válido"


def realizar_handshake(cliente, leitor, modo, protocolo, max_texto):
    client_isn = secrets.randbits(32)
    syn = {
        "tipo": "SYN",
        "syn": 1,
        "seq": client_isn,
        "ack": 0,
        "modo": modo,
        "protocolo": protocolo,
        "max_texto": max_texto,
    }
    enviar_msg(cliente, syn)
    print(f"SYN enviado (seq={client_isn})")

    syn_ack = receber_msg(leitor)
    valido, motivo = validar_syn_ack(syn_ack, client_isn, syn)
    if not valido:
        print("Handshake rejeitado.")
        print(f"Motivo: {motivo}")
        return None

    server_isn = syn_ack["seq"]
    ack = {
        "tipo": "ACK",
        "syn": 0,
        "seq": proximo_seq(client_isn),
        "ack": proximo_seq(server_isn),
    }
    enviar_msg(cliente, ack)
    print(f"ACK enviado (seq={ack['seq']}, ack={ack['ack']})")
    print("Handshake de três vias concluído; nenhuma mensagem de dados foi enviada.")

    return {
        "seq_inicial": proximo_seq(client_isn),
        "ack_servidor": proximo_seq(server_isn),
        "modo": syn_ack["modo"],
        "protocolo": syn_ack["protocolo"],
        "max_texto": syn_ack["max_texto"],
        "janela": syn_ack["janela"],
    }


def calcular_checksum(payload):
    return zlib.crc32(payload.encode("utf-8"))


def montar_pacotes(mensagem, tamanho, seq_inicial):
    pacotes = []
    inicios = range(0, len(mensagem), tamanho)
    for indice, inicio in enumerate(inicios):
        payload = mensagem[inicio:inicio + tamanho]
        pacotes.append({
            "tipo": "DATA",
            "seq": (seq_inicial + indice) % LIMITE_SEQ,
            "payload": payload,
            "checksum": calcular_checksum(payload),
            "fim": indice == len(inicios) - 1,
        })
    return pacotes


def pedir_mensagem(max_texto):
    while True:
        mensagem = input("[CLIENTE] Digite a mensagem (ou 'sair' para encerrar): ")
        if not mensagem:
            print("A mensagem não pode ser vazia.")
        elif len(mensagem) > max_texto:
            print(f"A mensagem tem {len(mensagem)} caracteres; o máximo é {max_texto}.")
        else:
            return mensagem


def pedir_tamanho_pacote(max_texto):
    while True:
        tamanho = escolher_inteiro("[CLIENTE] Tamanho dos lotes (qtd de caracteres)")
        if 1 <= tamanho <= max_texto:
            return tamanho
        print(f"O tamanho deve estar entre 1 e {max_texto}.")


def enviar_pacote(cliente, pacote):
    enviar_msg(cliente, pacote)
    print(colorir(f'[CLIENTE] Enviando pacote seq={pacote["seq"]} payload="{pacote["payload"]}"', AZUL))


def indice_do_ack(mensagem, seq_inicial, enviados):
    if mensagem.get("tipo") != "ACK" or not eh_inteiro(mensagem.get("ack")):
        return None
    indice = (mensagem["ack"] - seq_inicial) % LIMITE_SEQ
    return indice if indice < enviados else None


def tempo_ms(inicio):
    return round((time.monotonic() - inicio) * 1000)


def tratar_timeout(cliente, pacotes, protocolo, base, proximo, prazos):
    agora = time.monotonic()

    if protocolo == "GBN":
        print(colorir(f"[WARNING] Pacote {pacotes[base]['seq']} excedeu o tempo de envio. Reenviando...", VERMELHO))
        for indice in range(base, proximo):
            enviar_pacote(cliente, pacotes[indice])
            prazos[indice] = time.monotonic() + TIMEOUT
        return

    for indice in sorted(prazos):
        if prazos[indice] <= agora:
            print(colorir(f"[WARNING] Pacote {pacotes[indice]['seq']} excedeu o tempo de envio. Reenviando...", VERMELHO))
            enviar_pacote(cliente, pacotes[indice])
            prazos[indice] = time.monotonic() + TIMEOUT


def enviar_mensagem(cliente, leitor, sessao, seq_inicial, mensagem, tamanho):
    modo = sessao["modo"]
    protocolo = sessao["protocolo"]

    pacotes = montar_pacotes(mensagem, tamanho, seq_inicial)
    total = len(pacotes)
    janela = sessao["janela"] if modo == "lote" else 1

    base = 0
    proximo = 0
    confirmados = [False] * total
    prazos = {}
    inicio_envio = {}
    inicio_total = time.monotonic()

    while base < total:
        while proximo < total and proximo < base + janela:
            enviar_pacote(cliente, pacotes[proximo])
            inicio_envio[proximo] = time.monotonic()
            prazos[proximo] = inicio_envio[proximo] + TIMEOUT
            proximo += 1

        prazo = prazos[base] if protocolo == "GBN" else min(prazos.values())
        cliente.settimeout(max(0.001, prazo - time.monotonic()))
        try:
            resposta = receber_msg(leitor)
        except socket.timeout:
            tratar_timeout(cliente, pacotes, protocolo, base, proximo, prazos)
            continue
        finally:
            cliente.settimeout(None)

        indice = indice_do_ack(resposta, seq_inicial, proximo)
        if indice is None:
            continue

        if protocolo == "GBN":
            if indice < base:
                continue
            for confirmado in range(base, indice + 1):
                confirmados[confirmado] = True
                prazos.pop(confirmado, None)
                if modo == "individual":
                    print(colorir(f"[SUCCESS] Pacote enviado corretamente (ACK) time={tempo_ms(inicio_envio[confirmado])}ms", VERDE))
            base = indice + 1
        else:
            if confirmados[indice]:
                continue
            confirmados[indice] = True
            prazos.pop(indice, None)
            if modo == "individual":
                print(colorir(f"[SUCCESS] Pacote enviado corretamente (ACK) time={tempo_ms(inicio_envio[indice])}ms", VERDE))
            while base < total and confirmados[base]:
                base += 1

    if modo == "lote":
        print(colorir(f"[SUCCESS] Lote enviado corretamente (ACK) time={tempo_ms(inicio_total)}ms", VERDE))

    return (seq_inicial + total) % LIMITE_SEQ


def conversar(cliente, leitor, sessao):
    seq_atual = sessao["seq_inicial"]

    while True:
        print()
        mensagem = pedir_mensagem(sessao["max_texto"])
        if mensagem.strip().lower() == "sair":
            return seq_atual

        print(f"[CLIENTE] Modo: {NOMES_MODO[sessao['modo']]}")
        tamanho = pedir_tamanho_pacote(sessao["max_texto"])
        print()

        seq_atual = enviar_mensagem(cliente, leitor, sessao, seq_atual, mensagem, tamanho)


def encerrar_conexao(cliente, leitor, seq_fin):
    fin = {"tipo": "FIN", "seq": seq_fin}
    print()

    for _ in range(TENTATIVAS_FIN):
        enviar_msg(cliente, fin)
        print(f"[CLIENTE] FIN enviado (seq={seq_fin})")
        cliente.settimeout(TIMEOUT)
        try:
            while True:
                resposta = receber_msg(leitor)
                if resposta.get("tipo") == "FIN_ACK" and resposta.get("ack") == proximo_seq(seq_fin):
                    print("[CLIENTE] FIN-ACK recebido; conexão encerrada.")
                    return
        except socket.timeout:
            print(colorir("[WARNING] FIN sem resposta. Reenviando...", VERMELHO))
        finally:
            cliente.settimeout(None)

    print("[CLIENTE] O servidor não confirmou o encerramento.")


def main():
    os.system("")  # habilita cores no terminal do Windows

    print("Configuração da conexão")
    modo = escolher_opcao("Modo de operação", MODOS)
    protocolo = escolher_opcao("Protocolo", PROTOCOLOS)
    max_texto = escolher_inteiro("Tamanho máximo do texto")
    print()

    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        cliente.connect((HOST, PORT))
        cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"Conectado ao servidor {HOST}:{PORT}")
        leitor = LeitorMensagens(cliente)

        sessao = realizar_handshake(cliente, leitor, modo, protocolo, max_texto)
        if sessao is None:
            return

        print(f"Modo: {sessao['modo']}")
        print(f"Protocolo: {sessao['protocolo']}")
        print(f"Tamanho máximo do texto: {sessao['max_texto']}")
        print(f"Tamanho da janela: {sessao['janela']}")

        seq_fin = conversar(cliente, leitor, sessao)
        encerrar_conexao(cliente, leitor, seq_fin)

    except ConnectionRefusedError:
        print("Não foi possível conectar ao servidor.")
    except (ConnectionError, ValueError) as erro:
        print(f"Falha na comunicação: {erro}")
    finally:
        cliente.close()


if __name__ == "__main__":
    main()