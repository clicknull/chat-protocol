import logging
import socket
import sys
import threading
import select

logging.basicConfig(
    format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-2s  %(message)s',
    level=logging.DEBUG, filename=u'log.log')


class SocketWrapper(socket.socket):
    def __init__(self):
        super().__init__(socket.AF_INET, socket.SOCK_STREAM)
        self._handle_recv_data = True

    def my_send(self, msg):
        logging.info("SENT: " + msg + "\n")
        to_send = msg.encode("UTF-8")
        self.send(to_send)


class Server(SocketWrapper):
    amount_of_connections = 10  # How many users?
    buffer = 1024   # Chunk size?

    def __init__(self, ip, port):
        super().__init__()
        self.bind((ip, port))
        self.listen(Server.amount_of_connections)
        self.inner_threads = {}
        self.add_thread(self._handle_recv)

    def add_thread(self, target):
        thread = threading.Thread(target=target)
        self.inner_threads[target.__name__] = thread
        thread.start()

    def _handle_recv(self):
        inputs = [self]
        outputs = []
        message_queues = {}

        while self._handle_recv_data:
            readable, writable, exceptional = select.select(inputs, outputs,
                                                            inputs, 2)
            for sock in readable:
                if sock is self:
                    conn, addr = self.accept()
                    conn.setblocking(0)
                    inputs.append(conn)
                    message_queues[conn] = b''
                    logging.info('[+] Connection from: %s' % str(addr))
                else:
                    data = sock.recv(1024)
                    print(data)
                    if data:
                        message_queues[sock] += data
                        if sock not in outputs:
                            outputs.append(sock)
                    else:
                        if sock in outputs:
                            outputs.remove(sock)
                        inputs.remove(sock)
                        sock.close()
                        message_queues[sock] = message_queues[sock].decode(
                            'utf-8')
                        logging.info('[+] Recieved: %s' % message_queues[sock])
                        del message_queues[sock]


class Client(SocketWrapper):
    def __init__(self, ip, port):
        super().__init__()
        self.my_connect(ip, port)
        self.received_data = ""
        threading.Thread(target=self.get_back_info).start()

    def get_back_info(self):
        while self._handle_recv_data:
            self.get_data()
            logging.info("RECEIVED: " + self.received_data + "\n")

    def get_data(self):
        try:
            self.received_data = self.recv(1024).decode("UTF-8")
        except ConnectionResetError:    # Notification or smth
            print("The host has broken the connection")

    def my_connect(self, ip, port):
        try:
            self.connect((ip, port))
        except (TimeoutError, ConnectionRefusedError):
            print("Can't connect to the user")  # Should add user name. Need ip-user name assoc
        except InterruptedError:
            pass    # sys.exit() or smth
        except socket.gaierror:
            print("You don't have Internet access")
            sys.exit()
