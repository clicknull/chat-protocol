'''
Module contains two classes of handlers. In Handlers class
is placed all handling functionality. Handle class is additional
'''


import copy
import logging


LOGGER = logging.getLogger(__name__)


class Handlers:
    def __init__(self, peer):
        self._peer = peer
        self._create_table()

    def __getitem__(self, key):
        return self._table[key]

    def _create_table(self):
        '''
        Create table of handlers. In all below functions second parameter
        is "rpacket" -- response packet.
        '''

        self._table = {
            'connect': Handle(self._connect),
            'disconnect': Handle(self._disconnect),
            'ping': Handle(self._ping),
            'get_chat_info': Handle(self._get_chat_info),
            'chat_info': Handle(self._chat_info),
            'relay': Handle(self._relay)
        }

    def _connect(self, rpacket):
        pass

    def _disconnect(self, rpacket):
        pass

    def _ping(self, rpacket):
        pass

    def _get_chat_info(self, rpacket):
        '''
        If packet's type is 'get_chat_info' then new user want to
        fetch information about chat. In this case we should send it to
        him
        '''

        packet = self._peer._create_packet('chat_info', self._peer._id,
                                           -1, rpacket['to_host'],
                                           rpacket['from_host'])
        connected = []
        for host, data in self._peer.connected.items():
            _data = copy.deepcopy(data)
            _data['host'] = host
            connected.append(_data)
        packet['connected'] = connected

        print('[+] get_chat_info: Created response packet: %s' % packet)
        return packet

    def _chat_info(self, rpacket):
        '''
        Process information that we received on get_chat_info request
        '''

        ids = set()
        for host_data in rpacket['connected']:
            host = tuple(host_data['host'])
            _id = host_data['id']
            username = host_data['username']

            self._peer.connected[host] = {'id': _id, 'username': username}
            self._peer.id2host[_id] = host

            ids.add(_id)
        own_id = self._peer.generate_id(ids)
        self._peer._id = own_id

    def _relay(self, rpacket):
        pass


class Handle:
    def __init__(self, proc_func):
        self._proc_func = proc_func

    def handle(self, packet):
        return self._proc_func(packet)
