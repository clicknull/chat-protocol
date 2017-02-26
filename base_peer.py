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
import json
import traceback
import queue

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
        connected (set) Set of hosts that are connected to the chat
    '''

    def __init__(self, port):
        self._port = port
        self._recv_sock = self._create_recv_socket()
        self._opened_connection = {}

        self._init_threading_data()

        self._host = (self._fetch_IP_address(), port)
        print(self._host)

    def _init_threading_data(self):
        self._inner_workers = {}
        self._is_handle_recv = True

    def _add_work(self, work):
        ''' Run work in a new thread '''

        thread = threading.Thread(target=work)
        self._inner_workers[work.__name__] = thread
        thread.start()

    def _create_send_socket(self, timeout=2):
        ''' Create socket for sending messages '''

        send = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send.settimeout(timeout)
        return send

    def _create_recv_socket(self):
        ''' Create socket for receiving messages '''

        recv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        recv.bind(('', self._port))
        recv.listen(5)
        recv.setblocking(0)
        return recv

    def _send_temp_message(self, host, msg):
        ''' Used when happens greeting '''
        # print('TEST MESSAGE')
        if host not in self._opened_connection:
            self._open_connection(host, 10)
        sock = self._opened_connection[host]
        print('[+] Sending {} to {}'.format(repr(msg), str(host)))
        sock.sendall(json.dumps(msg).encode() + END_OF_MESSAGE)
        return sock

    def _close_connection(self, host):
        self._opened_connection[host].close()
        del self._opened_connection[host]

    def _open_connection(self, host, timeout=2):
        '''
        Open connection with a host

        Args:
            host (tuple) Tuple of IP and port of a host
        Return:
            (bool) True if connection is established else False
        '''

        try:
            send_sock = self._create_send_socket(timeout)
            send_sock.connect(host)
            self._opened_connection[host] = send_sock
            return True
        except socket.error as e:
            return False

    def _get_response(self, sock):
        resp = ''
        end_msg = END_OF_MESSAGE.decode()
        while True:
            data = sock.recv(BUFFER_SIZE).decode()
            resp += data
            if end_msg in data:
                break
        data = json.loads(resp)
        print('[+] Received: %s from %s\n' % (data, str(data['from_host'])))
        return data

    def _add_message2send(self, sock, msg):
        if sock not in self._outputs:
            self._outputs.append(sock)
        self._message_queues[sock].put(msg)

    def _accept_conn(self, sock):
        sock.setblocking(0)
        self._inputs.append(sock)
        self._message_data[sock] = b''
        self._message_queues[sock] = Queue()

    def _handle_recv(self):
        ''' Non-blocking handling of received data '''

        inputs = [self._recv_sock]
        outputs = []
        message_data = {}
        message_queues = {}

        self._inputs = inputs
        self._outputs = outputs
        self._message_data = message_data
        self._message_queues = message_queues

        while self._is_handle_recv:
            print('\n[*] Waiting for the next event')
            readable, writable, exceptional = select.select(inputs, outputs,
                                                            inputs, 2)
            self._process_readable_sock(inputs, outputs,
                                        message_data, readable)
            self._process_writable_sock(inputs, outputs,
                                        message_data, writable)
            # TODO PROCESS ERRORS WITH SOCKETS

    def _process_readable_sock(self, inputs, outputs, message_data, readable):
        ''' Process sockets that ready for reading '''

        for sock in readable:
            if sock is self._recv_sock:
                conn, addr = sock.accept()
                print('[*] New connection from %s' % str(addr))
                self._accept_conn(conn)
            else:
                data = sock.recv(BUFFER_SIZE)
                if data:
                    print('[+] Received {} from {}'
                          .format(repr(data.decode()), str(sock.getpeername())))
                    message_data[sock] += data
                    if END_OF_MESSAGE in data:
                        if sock not in outputs:
                            outputs.append(sock)
                        req = message_data[sock].decode()
                        message_data[sock] = b''

                        packet = self._update_opened_connection(req, sock)
                        self._message_queues[sock].put(self._process_request(packet, True))
                else:
                    self._close_sock(sock)

    def _close_sock(self, sock):
        print('[+] Closing {} after reading no data'
              .format(str(sock.getpeername())))
        if sock in self._outputs:
            self._outputs.remove(sock)

        self._inputs.remove(sock)
        sock.close()

        del self._message_data[sock]
        del self._message_queues[sock]

    def _process_writable_sock(self, inputs, outputs, message_data, writable):
        ''' Process sockets that ready for writing '''

        for sock in writable:
            try:
                next_msg = self._message_queues[sock].get_nowait()
            except queue.Empty:
                print('[*] Output queue for {} is empty'
                      .format(str(sock.getpeername())))
                outputs.remove(sock)
            else:
                if next_msg == b'""' + END_OF_MESSAGE:
                    continue
                print('[+] Sending {} to {}'
                      .format(repr(next_msg.decode()),
                              str(sock.getpeername())))
                sock.sendall(next_msg)

    def _update_opened_connection(self, req, sock):
        packet = json.loads(req)
        _type = packet['type']
        from_host = tuple(packet['from_host'])
        is_host_in = from_host not in self._opened_connection
        if is_host_in and _type in ['connect', 'find_insert_place']:
            self._opened_connection[from_host] = sock
        return packet

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
