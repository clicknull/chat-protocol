'''
Module includes BinaryTreePeer class that provides
structured peer-to-peer network
'''


import socket
import logging
import json
import traceback

from base_peer import BasePeer, END_OF_MESSAGE
from handlers import Handlers, TYPES

from random import randint


LOGGER = logging.getLogger(__name__)
DOWN = int(1e10)
UP = int(9e10)
INF = 1e11
SUCCESS_CONN = 'OK'


class BinaryTreePeer(BasePeer):
    def __init__(self, port, server_host=None):
        super().__init__(port)

        self._server_host = server_host
        self._create_handlers()

        # Attributes of node
        self._left = None
        self._right = None
        self._parent = None
        self._is_root = False

        self.up_bound = INF
        self.low_bound = -1

        # "left" or "right" node towards to parent node
        self._side = None
        self._neighbor = None

        self._init_data()

    def _init_data(self):
        self.connected = {}
        self.id2host = {}

        # Client attributes
        self._id = None
        self.username = None

    def _add_host(self, host, data):
        self.connected[host] = data

    def _get_self_data(self):
        return {'id': self._id, 'host': self._host, 'username': ''}

    def start(self):
        ''' Start peer's works and processing data '''

        self._add_work(self._handle_recv)

        # If we want to connect to existed chat
        if self._server_host is not None:
            self._greeting()
            self.connect(self._parent)
            self._inform_about_connected()
        else:
            self._id = self.generate_id([])
            self._is_root = True
            # TODO ADD USERNAME
            self._add_host(self._host, self._get_self_data())

    def _form_broadcast_field(self, side):
        return {'side': side}

    def _greeting(self):
        '''
        Make get_chat_info and find_insert_place requests to a server_host:

        1) Get chat information. Namely, list of connected hosts, their ids
        and so on.
        2) Fetch information about host that can process out connection to
        the chat
        '''

        greet_sock = self._create_send_socket()
        greet_sock.connect(self._server_host)

        self._get_chat_info(self._server_host, greet_sock)
        self._wait_node_data()
        self._find_insert_place(self._server_host, greet_sock)

        greet_sock.close()

    def connect(self, server_id):
        '''
        Connect to the chat.

        Args:
            server_host (tuple) IP and port of a host that will
                                handle our request for connection
        '''

        server_host = self.id2host[server_id]

        packet = self._create_packet(TYPES['connect'], -1, -1, self._host,
                                     server_host, connect=True)
        while True:
            print('[*] Connecting to %s\n' % str(server_host))
            sock = self._send_temp_message(server_host, packet)
            resp = self.__process_resp_sock(sock)
            if resp['response'] != SUCCESS_CONN:
                print('[-] Unsuccessful connecting. Trying to find another '
                      'insertion place in chat\n')
                self._close_connection(server_host)
                self._find_insert_place(self._server_host)
            else:
                print('[+] Connection with %s is established'
                      % str(server_host))
                self._accept_conn(sock)
                self._handlers['chat_info'].handle(resp)
                break

    def disconnect(self):
        '''
        Disconnect from the chat. Send to all users that we
        are disconnecting.
        '''
        pass

    def _inform_about_connected(self):
        ''' Inform other clients of chat that user was connected '''
        packet = self._create_packet('new_user', self._id, -1,
                                     self._host, -1, broadcast=True)
        packet['broadcast']['user_info'] = self._get_self_data()
        self.send_broadcast_message(packet)

    def __fetch_and_process_greet(self, packet, server_host, print_msg,
                                  sock=None):
        if sock is None:
            sock = self._create_send_socket()
            sock.connect(server_host)
        print(print_msg)
        sock.sendall(json.dumps(packet).encode() + END_OF_MESSAGE)
        return self.__process_resp_sock(sock)

    def __process_resp_sock(self, sock):
        resp = self._get_response(sock)
        return self._handle_resp_by_type(resp)

    def _get_chat_info(self, server_host, sock=None):
        '''
        Get chat information. Namely, list of connected hosts, their ids
        and so on.
        '''
        packet = self._create_packet(TYPES['get_chat_info'], -1, -1,
                                     self._host, server_host)
        print_msg = ('[*] Sending get_chat_information request {} to {}\n'
                     .format(packet, str(server_host)))
        return self.__fetch_and_process_greet(packet, server_host, print_msg,
                                              sock)


    def _find_insert_place(self, server_host, sock=None):
        '''
        Fetch information about host that can process out connection to
        the chat
        '''
        packet = self._create_packet(TYPES['find_insert_place'], self._id,
                                   self.connected[server_host]['id'],
                                   self._host, server_host)
        print_msg = ('[*] Sending find_insert_place request {} to {}\n'
                     .format(packet, str(server_host)))
        return self.__fetch_and_process_greet(packet, server_host,
                                              print_msg, sock)

    def _handle_resp_by_type(self, resp):
        return self._handlers[resp['type']].handle(resp)

    def _create_handlers(self):
        self._handlers = Handlers(self)

    def _create_packet(self, _type, from_id, to_id, from_host, to_host,
                       broadcast=False, connect=False):
        '''
        Form a chat packet.

        Args:
            type      (str) Type of packet: connect, get_chat_info, ping,
                            disconnect and etc. All list of types you can find
                            on project's github page.
            from_id   (int) Id of a sender
            from_host (tuple) Tuple of IP and port of a sender host
            to_id     (int) Id of a receiver
            to_host   (tuple) IP and port of a receiver host
            broadcast (dict) If packet is broadcast then this is field is
                             necessary

        Return:
            (dict) Formed packet
        '''

        packet = {
            'type': _type,
            'from_id': from_id,
            'to_id': to_id,
            'from_host': from_host,
            'to_host': to_host
        }
        if broadcast:
            packet['broadcast'] = {}
        if connect:
            packet['place_info'] = self._place_info
            packet['user_info'] = {'id': self._id, 'host': self._host,
                                   'username': ''}
        return packet

    def send_message(self, host, msg):
        '''
        Send message to a host in the chat.

        Args:
            host (tuple) Tuple of IP and port of a host
            msg (dict) Message that is sended

        Return:
            (bool) True if transfer was successful else False
        '''

        try:
            host_id = self.connected[host]['id']

            left = self.id2host.get(self._left, None)
            right = self.id2host.get(self._right, None)
            parent = self.id2host.get(self._parent, None)

            if self.low_bound < host_id < self.up_bound:
                side = left if self._id > host_id else right
                sock = self._opened_connection[side]
            else:
                sock = self._opened_connection[parent]
            self._add_message2send(sock, json.dumps(msg).encode() + END_OF_MESSAGE)
            return True
        except KeyError as e:
            # TODO PROCESS THIS CASE CORRECTLY
            traceback.print_exc()
            return False
        except socket.error as e:
            # TODO PROCESS THIS CASE CORRECTLY
            traceback.print_exc()
            return False

    def send_broadcast_message(self, msg, closed=[]):
        ''' Broadcast transfering of message '''
        neighbors = [self._left, self._right, self._parent]
        locations = ['parent', 'parent', self._side]

        for host_id, side in zip(neighbors, locations):
            if host_id in closed or host_id is None:
                continue
            host = self.id2host[host_id]
            msg['to_id'] = host_id
            msg['to_host'] = host
            msg['broadcast']['from_node_side'] = side
            print('[*] Sending broadcast message to %s\n' % host_id)
            self.send_message(host, msg)

    def _process_request(self, request, loaded=False):
        '''
        Process request from another client. First of all we
        should decrypt message via encryptor.

        Args:
            request (string) Request from some client in the chat
            loaded (bool) If request is json loaded
        Return:
            (bytes) Response to request
        '''
        packet = request

        if not loaded:
            packet = json.loads(request)

        # All payload are placed in Handlers class
        resp_packet = self._handle_resp_by_type(packet)
        if resp_packet in [None, True, False]:
            resp_packet = ''

        return  json.dumps(resp_packet).encode() + END_OF_MESSAGE

    def _wait_node_data(self):
        ''' Wait for assignment of id '''
        while self._id is None:
            pass

    def generate_id(self, ids):
        while True:
            _id = randint(DOWN, UP)
            if _id not in ids:
                self.id2host[_id] = self._host
                return _id
