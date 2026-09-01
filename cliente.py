import socket

HOST = "127.0.0.1"
PORT = 2000


def main():
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        cliente.connect((HOST, PORT))
        print(f"Não foi possivel conectar ao server")

    finally:
        cliente.close()


    if __name__ == "__main__":
        main()
