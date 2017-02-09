'''
Module includes BinaryTreePeer class that provides
structured peer-to-peer network
'''


import socket
import logging
import json

from base_peer import BasePeer
from handlers import Handlers


LOGGER = logging.getLogger(__name__)


class BinaryTreePeer(BasePeer):
    def __init__(self, port, server_host=None):
        super().__init__(self, port)

        self._server_host = server_host
        self._id = None

        # Attributes of node
        self._left = None
        self._right = None
        self._parent = None

        # "left" or "right" node towards to parent node
        self._cur_pos = None

    def start(self):
        ''' Start peer's works and processing data '''

        self._add_work(self._handle_recv)

        # If we want to connect to existed chat
        if self._server_host is not None:
            self._get_chat_info(self._server_host)
            self._fill_node_data()
            self.connect(self._server_host)

    def _form_broadcast_field(self, side):
        return {'side': side}

    def _create_handlers(self):
        self._handlers = Handlers(self)

    def _create_packet(self, _type, from_id, to_id, from_host, to_host,
                       broadcast=None):
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
            packet['broadcast'] = broadcast
        return packet

    def connect(self, server_host):
        '''
        Connect to the chat.

        Args:
            server_host (tuple) IP and port of a host that will
                                handle our request for connection
        '''

        LOGGER.info('[*] Connecting to: %s' % str(server_host))
        packet = self._create_packet(_type='connect', -1, 1, self._host,
                                     server_host)
        self.send_message(server_host, packet)

    def disconnect(self):
        '''
        Disconnect from the chat. Send to all users that we
        are disconnecting.
        '''
        pass

    def _get_chat_info(self, server_host):
        '''
        Get chat information. Namely, list of connected hosts, their ids
        and so on.

        Args:
            server_host (tuple) IP and port of a server host
        '''
        packet = self._create_packet(_type='get_chat_info', -1, -1,
                                     self._host, server_host)
        self.send_message(server_host, packet)

    def _fill_node_data(self):
        '''
        Fill node's data, namely id.
        '''
        pass


    def _process_request(self, request):
        '''
        Process request from another client. First of all we
        should decrypt message via encryptor.

        Args:
            request (string) Request from some client in the chat
        Return:
            (bytes) Response to request
        '''

        packet = json.loads(request)

        # All payload are placed in Handlers class
        return self._handlers[packet['type']].handle(packet)
