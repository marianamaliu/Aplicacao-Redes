# recepcao, validacao e aprovacao
import socket
import json
import secrets
import queue
import os
import sys

from protocolo import (
    LIMITE_SEQ, MODOS, PROTOCOLOS, FIM_TECLADO, LeitorMensagens, Conexao,
    eh_inteiro, proximo_seq, enviar_msg, receber_msg, iniciar_teclado, conversar,
)

HOST = "0.0.0.0"  # todas as interfaces (nao so localhost)
PORT = 2000
JANELA_INICIAL = 5
TAMAN_MIN_TEXTO = 30 #texto


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
        "seq_envio": proximo_seq(server_isn),
        "seq_recebimento": proximo_seq(client_isn),
        "modo": syn["modo"],
        "protocolo": syn["protocolo"],
        "max_texto": syn["max_texto"],
        "janela": JANELA_INICIAL,
    }


def aguardar_cliente(servidor, teclado):
    while True:
        try:
            return servidor.accept()
        except socket.timeout:
            pass

        while True:
            try:
                linha = teclado.get_nowait()
            except queue.Empty:
                break
            if linha is not FIM_TECLADO and linha.strip():
                print("Nenhum cliente conectado; a mensagem não foi enviada.")


def atender_cliente(conexao, endereco, teclado):
    conexao.settimeout(None)
    conexao.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print(f"Cliente conectado: {endereco}")
    leitor = LeitorMensagens(conexao)

    try:
        sessao = realizar_handshake(conexao, leitor)
    except (ConnectionError, ValueError) as erro:
        print(f"Falha no handshake: {erro}")
        conexao.close()
        return

    if sessao is None:
        conexao.close()
        return

    conversar(Conexao(conexao, leitor, "SERVIDOR", sessao), teclado, sair_no_fim_do_teclado=False)


def main():
    os.system("")  # habilita cores no terminal do Windows

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PORT))
    servidor.listen(1)
    servidor.settimeout(1.0)  # permite fechar com Ctrl+C no Windows

    teclado = iniciar_teclado()

    try:
        while True:
            print(f"server aguardando conexão em {HOST}:{PORT} (Ctrl+C para encerrar)\n")
            conexao, endereco = aguardar_cliente(servidor, teclado)
            atender_cliente(conexao, endereco, teclado)
            print()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        servidor.close()


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)