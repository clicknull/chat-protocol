'''
There is placed base class for peer

Vars:
    INTERFACES (list) List of Unix network interfaces
    BUFFER_SIZE (int) Size of receiving socket buffer
'''


import socket
import select

from collections import namedtuple


INTERFACES = ['eth', 'wlan', 'en', 'wl']
BUFFER_SIZE = 1024
END_OF_MESSAGE = '\r\n'


class BasePeer:
    ''' Class for base functionality of every peer '''
    # TODO ADD LOGGING

    def __init__(self, port):
        self._port = port
        self._recv_sock = self._create_recv_socket()

    def _init_threading_data(self):
        self._is_handle_recv = True

    def _create_send_socket(self):
        ''' Create socket for sending messages '''

        send = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send.settimeout(2)
        return send

    def _create_recv_socket(self):
        ''' Create socket for receiving messages '''

        recv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        recv.bind(('', self._port))
        recv.listen(5)
        recv.setblocking(0)
        return recv

    def _handle_recv(self):
        ''' Non-blocking handling of received data '''

        msg = namedtuple('Message', 'out data')

        inputs = [self._recv_sock]
        outputs = []
        message_queues = {}

        while self._is_handle_recv:
            readable, writable, exceptional = select.select(inputs, outputs,
                                                            inputs, 2)
            self._process_readable_sock(inputs, outputs,
                                        message_queues, readable)
            self._process_writable_sock(inputs, outputs,
                                        message_queues, writable)

    def _process_readable_sock(self, inputs, outputs, message_queues, readable):
        ''' Process sockets that ready for reading '''

        for sock in readable:
            if sock is self._recv_sock:
                conn, addr = sock.accept()
                conn.setblocking(0)
                inputs.append(conn)
                message_queues[conn] = b''
            else:
                data = sock.recv(BUFFER_SIZE)
                if data:
                    message_queues[sock].data += data
                    if sock not in outputs:
                        outputs.append(sock)
                    if END_OF_MESSAGE in data.decode('utf-8'):
                        message_queues[sock].out = True
                        req = message_queues[sock].data.decode('utf-8')
                        message_queues[sock].data = self._process_request(req)
                else:
                    if sock in outputs:
                        outputs.remove(sock)
                    inputs.remove(sock)
                    sock.close()
                    del message_queues[sock]

    def _process_writable_sock(self, inputs, outputs, message_queues, writable):
        ''' Process sockets that ready for writing '''

        for sock in writable:
            if sock not in message_queues:
                outputs.remove(sock)
            else:
                msg = message_queues[sock]
                if msg.out:
                    sock.send(msg.data)

    def _process_request(self, request):
        '''
        Process request from another client. First of all we
        should decrypt message via encryptor.

        Args:
            request (string) Request from some client in the chat
        Return:
            (bytes) Response to request
        '''

        # TODO REQUEST PROCESSING
        pass
