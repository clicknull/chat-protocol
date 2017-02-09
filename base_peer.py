'''
There is placed BasePeer class. It provides base functionality
of every peer-to-peer network.

Vars:
    INTERFACES (list) List of Unix network interfaces
    BUFFER_SIZE (int) Size of receiving socket buffer
'''

import os
import socket
import select
import logging
import time
import threading
import netifaces as nf

from queue import Queue

from collections import namedtuple


INTERFACES = ['eth', 'wlan', 'en', 'wl']
BUFFER_SIZE = 1024
LOGGER = logging.getLogger(__name__)
END_OF_MESSAGE = b'\r\n'


class BasePeer:
    '''
    Class for base functionality of every peer

    Fields:
        port (int) Port for receiving connections
        _recv_sock (socket) Socket for receiving messages
        _opened_connection (dict) Matching between a host and
                                  socket with connection to a host
        _host (tuple) Tuple of IP and port of current machine
        _connected (set) Set of hosts that are connected to the chat
    '''

    def __init__(self, port):
        self._port = port
        self._recv_sock = self._create_recv_socket()
        self._opened_connection = {}

        self._init_threading_data()

        self._host = (self._fetch_IP_address(), port)
        self._connected = set()

        # Add current host in set of connected hosts
        self.add_host(self._host)

    def _init_threading_data(self):
        self._inner_workers = {}
        self._is_handle_recv = True

    def _add_work(self, work):
        ''' Run work in a new thread '''

        thread = threading.Thread(target=work)
        self._inner_workers[work.__name__] = thread
        thread.start()

    def _add_host(self, host):
        self._connected.add(host)

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

    def _open_connection(self, host):
        '''
        Open connection with a host

        Args:
            host (tuple) Tuple of IP and port of a host
        Return:
            (bool) True if connection is established else False
        '''

        try:
            send_sock = self._create_send_socket()
            send_sock.connect(host)
            self._opened_connection[host] = send_sock
            return True
        except socket.error as e:
            return False

    def send_message(self, host, msg):
        '''
        Send message to a host in the chat.

        Args:
            host (tuple) Tuple of IP and port of a host
            msg (str) Message that is sended

        Return:
            (bool) True if transfer was successful else False
        '''

        if host not in self._opened_connection:
            if not self._open_connection(host):
                return False
        try:
            send_sock = self._opened_connection[host]
            send_sock.send(json.dumps(msg).encode())
            return True
        except KeyError as e:
            return False

    def _handle_recv(self):
        ''' Non-blocking handling of received data '''

        inputs = [self._recv_sock]
        outputs = []
        message_queues = {}

        while self._is_handle_recv:
            LOGGER.info('\n[*] Waiting for the next event')
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
                LOGGER.info('[*] New connection from %s' % str(addr))
                conn.setblocking(0)
                inputs.append(conn)
                message_queues[conn] = {'out': False, 'data': b''}
                self._opened_connection[addr] = conn
            else:
                data = sock.recv(BUFFER_SIZE)
                if data:
                    LOGGER.info('[+] Received {} from {}'
                                .format(repr(data.decode()), str(sock.getpeername())))
                    message_queues[sock]['data'] += data
                    if sock not in outputs:
                        outputs.append(sock)
                    if END_OF_MESSAGE in data:
                        message_queues[sock]['out'] = True
                        req = message_queues[sock]['data'].decode('utf-8')
                        message_queues[sock]['data'] = self._process_request(req)
                else:
                    LOGGER.info('[+] Closing {} after reading no data'
                                .format(str(sock.getpeername())))
                    if sock in outputs:
                        outputs.remove(sock)

                    inputs.remove(sock)
                    del self._opened_connection[sock.getpeername()]
                    sock.close()

                    del message_queues[sock]

    def _process_writable_sock(self, inputs, outputs, message_queues, writable):
        ''' Process sockets that ready for writing '''

        for sock in writable:
            next_msg = message_queues[sock]['data']
            if next_msg == b'':
                LOGGER.info('[*] Output queue for {} is empty'
                            .format(str(sock.getpeername())))
                outputs.remove(sock)
            else:
                if message_queues[sock]['out']:
                    message_queues[sock]['data'] = b''
                    message_queues[sock]['out'] = False
                    LOGGER.info('[*] Sending {} to {}'
                                .format(repr(next_msg.decode()),
                                        str(sock.getpeername())))
                    sock.send(next_msg)

    def _fetch_IP_address(self):
        os_name = os.name
        for glob_if in nf.interfaces():
            try:
                address = nf.ifaddresses(glob_if)[2][0]['addr']
                if os_name == 'nt':
                    return address
                for loc_of in INTERFACES:
                    if glob_if.startswith(loc_of):
                        return address
            except KeyError:
                pass
