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

def receber_msg(socket_conexao): #ler os dados
    texto_recebido = ""
    while True:
        pedaco=socket_conexao.recv(1) #recv: metodo que le os dados que chegam pela rede (1: 1 byte)

        if not pedaco:
            raise ConnectionError("Conexão encerrada antes do esperado")

        texto_recebido+=pedaco.decode("utf-8") #converte para a string de volta 

        if texto_recebido.endswith("\n"):
            break

    return json.loads(texto_recebido.strip()) #converte do formato json p dicinario python. 
    
    