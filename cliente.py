import socket
import secrets
import os
import sys

from protocolo import (
    LIMITE_SEQ, MODOS, PROTOCOLOS, LeitorMensagens, Conexao,
    eh_inteiro, proximo_seq, enviar_msg, receber_msg, iniciar_teclado, conversar,
)

HOST = "127.0.0.1"
PORT = 2000


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
        "seq_envio": proximo_seq(client_isn),
        "seq_recebimento": proximo_seq(server_isn),
        "modo": syn_ack["modo"],
        "protocolo": syn_ack["protocolo"],
        "max_texto": syn_ack["max_texto"],
        "janela": syn_ack["janela"],
    }


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
            cliente.close()
            return

        print(f"Modo: {sessao['modo']}")
        print(f"Protocolo: {sessao['protocolo']}")
        print(f"Tamanho máximo do texto: {sessao['max_texto']}")
        print(f"Tamanho da janela: {sessao['janela']}")

        conexao = Conexao(cliente, leitor, "CLIENTE", sessao)
        conversar(conexao, iniciar_teclado())

    except ConnectionRefusedError:
        print("Não foi possível conectar ao servidor.")
        cliente.close()
    except (ConnectionError, ValueError) as erro:
        print(f"Falha na comunicação: {erro}")
        cliente.close()
    except KeyboardInterrupt:
        print("\nCliente encerrado.")
        cliente.close()


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)