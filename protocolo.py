import socket
import json
import queue
import threading
import time
import zlib

LIMITE_SEQ = 1 << 32
MODOS = ["individual", "lote"]
PROTOCOLOS = ["GBN", "SR"]
NOMES_MODO = {"individual": "isolado", "lote": "em lote"}
TIMEOUT = 1.0
TENTATIVAS_FIN = 5

AZUL = "\033[94m"
VERMELHO = "\033[91m"
VERDE = "\033[92m"
AMARELO = "\033[93m"
RESET = "\033[0m"

FIM_TECLADO = object()


def colorir(texto, cor):
    return f"{cor}{texto}{RESET}"


def eh_inteiro(valor):
    return type(valor) is int


def proximo_seq(numero):
    return (numero + 1) % LIMITE_SEQ


def calcular_checksum(payload):
    return zlib.crc32(payload.encode("utf-8"))


class LeitorMensagens:
    def __init__(self, socket_conexao):
        self.socket = socket_conexao
        self.buffer = b""

    def ler_linha(self):
        while b"\n" not in self.buffer:
            dados = self.socket.recv(4096)
            if not dados:
                raise ConnectionError("Conexão encerrada pelo outro lado")
            self.buffer += dados
        linha, _, self.buffer = self.buffer.partition(b"\n")
        return linha.decode("utf-8")


def enviar_msg(socket_conexao, mensagem):
    linha = json.dumps(mensagem, ensure_ascii=False) + "\n"
    socket_conexao.sendall(linha.encode("utf-8"))


def receber_msg(leitor):
    mensagem = json.loads(leitor.ler_linha())
    if not isinstance(mensagem, dict):
        raise ValueError("Mensagem recebida não é um objeto JSON")
    return mensagem


def pacote_valido(mensagem):
    return (
        eh_inteiro(mensagem.get("seq"))
        and isinstance(mensagem.get("payload"), str)
        and eh_inteiro(mensagem.get("checksum"))
        and isinstance(mensagem.get("fim"), bool)
    )


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


def tempo_ms(inicio):
    return round((time.monotonic() - inicio) * 1000)


class Conexao:
    def __init__(self, socket_conexao, leitor, nome, sessao):
        self.socket = socket_conexao
        self.leitor = leitor
        self.nome = nome
        self.modo = sessao["modo"]
        self.protocolo = sessao["protocolo"]
        self.max_texto = sessao["max_texto"]
        self.janela = sessao["janela"] if self.modo == "lote" else 1
        self.seq_envio = sessao["seq_envio"]
        self.seq_recebimento = sessao["seq_recebimento"]

        self.trava_envio = threading.Lock()
        self.acks = queue.Queue()
        self.fin_acks = queue.Queue()
        self.encerrada = threading.Event()
        self.fechando = False

        self.esperado = 0
        self.partes = []
        self.fora_de_ordem = {}
        self.thread = threading.Thread(target=self._receber, daemon=True)

    def log(self, texto, cor=None):
        linha = f"[{self.nome}] {texto}"
        print(colorir(linha, cor) if cor else linha, flush=True)

    def aviso(self, texto):
        print(colorir(f"[WARNING] {texto}", VERMELHO), flush=True)

    def sucesso(self, texto):
        print(colorir(f"[SUCCESS] {texto}", VERDE), flush=True)

    def iniciar(self):
        self.thread.start()

    def fechar(self):
        self.fechando = True
        self.encerrada.set()
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()
        if self.thread.is_alive():
            self.thread.join(timeout=2)

    def _perder(self, erro):
        if not self.encerrada.is_set() and not self.fechando:
            self.aviso(f"Conexão perdida: {erro}")
        self.encerrada.set()

    def _enviar(self, mensagem):
        linha = (json.dumps(mensagem, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            with self.trava_envio:
                self.socket.sendall(linha)
            return True
        except OSError as erro:
            self._perder(erro)
            return False


    def _enviar_pacote(self, pacote):
        self.log(f'Enviando pacote seq={pacote["seq"]} payload="{pacote["payload"]}"', AZUL)
        self._enviar(pacote)

    def _tratar_timeout(self, pacotes, base, proximo, prazos):
        agora = time.monotonic()

        if self.protocolo == "GBN":
            self.aviso(f"Pacote {pacotes[base]['seq']} excedeu o tempo de envio. Reenviando...")
            for indice in range(base, proximo):
                self._enviar_pacote(pacotes[indice])
                prazos[indice] = time.monotonic() + TIMEOUT
            return

        for indice in sorted(prazos):
            if prazos[indice] <= agora:
                self.aviso(f"Pacote {pacotes[indice]['seq']} excedeu o tempo de envio. Reenviando...")
                self._enviar_pacote(pacotes[indice])
                prazos[indice] = time.monotonic() + TIMEOUT

    def enviar_mensagem(self, mensagem, tamanho):
        seq_inicial = self.seq_envio
        pacotes = montar_pacotes(mensagem, tamanho, seq_inicial)
        total = len(pacotes)

        base = 0
        proximo = 0
        confirmados = [False] * total
        prazos = {}
        inicio_envio = {}
        inicio_lote = time.monotonic()

        while base < total:
            if self.encerrada.is_set():
                return False

            if base == proximo:
                fim_lote = min(total, proximo + self.janela)
                inicio_lote = time.monotonic()
                while proximo < fim_lote:
                    self._enviar_pacote(pacotes[proximo])
                    inicio_envio[proximo] = time.monotonic()
                    prazos[proximo] = inicio_envio[proximo] + TIMEOUT
                    proximo += 1

            prazo = prazos[base] if self.protocolo == "GBN" else min(prazos.values())
            try:
                ack = self.acks.get(timeout=max(0.0, prazo - time.monotonic()))
            except queue.Empty:
                self._tratar_timeout(pacotes, base, proximo, prazos)
                continue

            indice = (ack - seq_inicial) % LIMITE_SEQ
            if indice >= proximo:
                continue

            if self.protocolo == "GBN":
                if indice < base:
                    continue
                for confirmado in range(base, indice + 1):
                    confirmados[confirmado] = True
                    prazos.pop(confirmado, None)
                    if self.modo == "individual":
                        self.sucesso(f"Pacote enviado corretamente (ACK) time={tempo_ms(inicio_envio[confirmado])}ms")
                base = indice + 1
            else:
                if confirmados[indice]:
                    continue
                confirmados[indice] = True
                prazos.pop(indice, None)
                if self.modo == "individual":
                    self.sucesso(f"Pacote enviado corretamente (ACK) time={tempo_ms(inicio_envio[indice])}ms")
                while base < total and confirmados[base]:
                    base += 1

            if self.modo == "lote" and base == proximo:
                self.sucesso(f"Lote enviado corretamente (ACK) time={tempo_ms(inicio_lote)}ms")

        self.seq_envio = (seq_inicial + total) % LIMITE_SEQ
        return True

    def encerrar(self):
        if self.encerrada.is_set():
            return
        self.fechando = True
        seq_fin = self.seq_envio
        print()

        for _ in range(TENTATIVAS_FIN):
            self.log(f"FIN enviado (seq={seq_fin})")
            if not self._enviar({"tipo": "FIN", "seq": seq_fin}):
                return
            prazo = time.monotonic() + TIMEOUT
            while time.monotonic() < prazo:
                try:
                    ack = self.fin_acks.get(timeout=max(0.0, prazo - time.monotonic()))
                except queue.Empty:
                    break
                if ack == proximo_seq(seq_fin):
                    self.log("FIN-ACK recebido; conexão encerrada.")
                    self.encerrada.set()
                    return
            if self.encerrada.is_set():
                return
            self.aviso("FIN sem resposta. Reenviando...")

        self.log("O outro lado não confirmou o encerramento.")


    def _receber(self):
        try:
            while True:
                mensagem = receber_msg(self.leitor)
                tipo = mensagem.get("tipo")

                if tipo == "ACK":
                    if eh_inteiro(mensagem.get("ack")):
                        self.acks.put(mensagem["ack"])
                elif tipo == "FIN_ACK":
                    self.fin_acks.put(mensagem.get("ack"))
                elif tipo == "FIN":
                    self._tratar_fin(mensagem)
                elif tipo == "DATA" and pacote_valido(mensagem):
                    self._tratar_dado(mensagem)
                else:
                    self.aviso("Mensagem fora do formato esperado. Ignorada.")
        except (ConnectionError, ValueError, OSError) as erro:
            self._perder(erro)

    def _tratar_fin(self, mensagem):
        seq_fin = (self.seq_recebimento + self.esperado) % LIMITE_SEQ
        if mensagem.get("seq") != seq_fin:
            self.aviso(f"FIN com seq inesperado ({mensagem.get('seq')}). Ignorado.")
            return

        self._enviar({"tipo": "FIN_ACK", "ack": proximo_seq(seq_fin)})
        if not self.encerrada.is_set():
            print()
            if self.partes:
                self.aviso("Conexão encerrada com uma mensagem incompleta.")
            self.log("FIN recebido e confirmado; o outro lado encerrou a conexão.")
            self.encerrada.set()

    def _entregar(self, payload, ultimo):
        self.partes.append(payload)
        if ultimo:
            mensagem_completa = "".join(self.partes)
            self.partes.clear()
            self.log(f'Mensagem completa: "{mensagem_completa}"', VERDE)
            print()

    def _tratar_dado(self, mensagem):
        seq = mensagem["seq"]
        payload = mensagem["payload"]
        indice = (seq - self.seq_recebimento) % LIMITE_SEQ
        checksum = calcular_checksum(payload)

        if checksum != mensagem["checksum"]:
            self.aviso(
                f"Pacote seq={seq} corrompido "
                f"(checksum recebido=0x{mensagem['checksum']:08X}, calculado=0x{checksum:08X}). Descartado."
            )
            if self.protocolo == "GBN" and self.esperado > 0:
                self._enviar({"tipo": "ACK", "ack": (self.seq_recebimento + self.esperado - 1) % LIMITE_SEQ})
            return

        if self.modo == "lote":
            self.log(f'Pacote recebido: seq={seq} checksum=0x{checksum:08X} payload="{payload}"', AMARELO)
        else:
            self.log(f"Pacote recebido: seq={seq} checksum=0x{checksum:08X}", AMARELO)

        if self.protocolo == "GBN":
            if indice == self.esperado:
                self.esperado += 1
                self._enviar({"tipo": "ACK", "ack": seq})
                self._entregar(payload, mensagem["fim"])
            else:
                self.aviso(f"Pacote seq={seq} fora de ordem. Descartado.")
                if self.esperado > 0:
                    self._enviar({"tipo": "ACK", "ack": (self.seq_recebimento + self.esperado - 1) % LIMITE_SEQ})
        else:
            if self.esperado <= indice < self.esperado + self.janela:
                self.fora_de_ordem[indice] = (payload, mensagem["fim"])
                self._enviar({"tipo": "ACK", "ack": seq})
                while self.esperado in self.fora_de_ordem:
                    trecho, ultimo = self.fora_de_ordem.pop(self.esperado)
                    self.esperado += 1
                    self._entregar(trecho, ultimo)
            elif indice < self.esperado:
                self._enviar({"tipo": "ACK", "ack": seq})



def iniciar_teclado():
    fila = queue.Queue()

    def ler():
        while True:
            try:
                linha = input()
            except (EOFError, KeyboardInterrupt, OSError):
                fila.put(FIM_TECLADO)
                return
            fila.put(linha)

    threading.Thread(target=ler, daemon=True).start()
    return fila


def proxima_linha(fila, conexao):
    while not conexao.encerrada.is_set():
        try:
            return fila.get(timeout=0.2)
        except queue.Empty:
            continue
    return None


def pedir_tamanho(fila, conexao):
    while True:
        conexao.log("Tamanho dos lotes (qtd de caracteres):")
        linha = proxima_linha(fila, conexao)
        if linha is None or linha is FIM_TECLADO:
            return linha
        linha = linha.strip()
        if linha.isdigit() and 1 <= int(linha) <= conexao.max_texto:
            return int(linha)
        print(f"O tamanho deve ser um número entre 1 e {conexao.max_texto}.")


def esperar_encerramento(conexao):
    while not conexao.encerrada.wait(0.2):
        pass


def conversar(conexao, fila, sair_no_fim_do_teclado=True):
    conexao.iniciar()
    print()

    try:
        while True:
            conexao.log("Digite a mensagem (ou 'sair' para encerrar):")
            linha = proxima_linha(fila, conexao)

            if linha is FIM_TECLADO or (isinstance(linha, str) and linha.strip().lower() == "sair"):
                if linha is FIM_TECLADO and not sair_no_fim_do_teclado:
                    esperar_encerramento(conexao)
                else:
                    conexao.encerrar()
                return
            if linha is None:
                return
            if not linha:
                print("A mensagem não pode ser vazia.")
                continue
            if len(linha) > conexao.max_texto:
                print(f"A mensagem tem {len(linha)} caracteres; o máximo é {conexao.max_texto}.")
                continue

            conexao.log(f"Modo: {NOMES_MODO[conexao.modo]}")
            tamanho = pedir_tamanho(fila, conexao)
            if tamanho is None:
                return
            if tamanho is FIM_TECLADO:
                if sair_no_fim_do_teclado:
                    conexao.encerrar()
                else:
                    esperar_encerramento(conexao)
                return

            print()
            if not conexao.enviar_mensagem(linha, tamanho):
                return
    finally:
        conexao.fechar()    