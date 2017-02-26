'''
Module contains two classes of handlers. In Handlers class
is placed all handling functionality. Handle class is additional

Vars:
    TYPES (dict) If names of package types will be changed then it
                 needs to be changed in this dictionary
'''


import copy
import logging


LOGGER = logging.getLogger(__name__)
TYPES = {
    'connect': 'connect',
    'disconnect': 'disconnect',
    'ping': 'ping',
    'get_chat_info': 'get_chat_info',
    'chat_info': 'chat_info',
    'relay': 'relay',
    'find_insert_place': 'find_insert_place',
    'insert_place': 'insert_place',
    'downtype': 'downtype',
    'connect_resp': 'connect_resp',
    'new_user': 'new_user'
}


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
            TYPES['connect']: Handle(self._connect),
            TYPES['disconnect']: Handle(self._disconnect),
            TYPES['ping']: Handle(self._ping),
            TYPES['get_chat_info']: Handle(self._get_chat_info),
            TYPES['chat_info']: Handle(self._chat_info),
            TYPES['relay']: Handle(self._relay),
            TYPES['find_insert_place']: Handle(self._find_insert_place),
            TYPES['insert_place']: Handle(self._insert_place),
            TYPES['connect_resp']: Handle(self._connect_resp),
            TYPES['new_user']: Handle(self._new_user)
        }

    def _connect(self, rpacket):
        ''' Handle connection request '''

        place_info = rpacket['place_info']
        side = place_info['side']
        user_info = rpacket['user_info']
        is_successful = False
        if side == 'left' and self._peer._left is None:
            self._peer._left = user_info['id']
            is_successful = True
        elif side == 'right' and self._peer._right is None:
            self._peer._right = user_info['id']
            is_successful = True
        else:
            pass
        packet = self._reverse_packet(rpacket, 'connect_resp')
        if is_successful:
            self._add_user_to_chat(user_info)

            packet['response'] = 'OK'
            packet['connected'] = self._get_connected()
        else:
            packet['response'] = 'ERROR'
        del packet['user_info']
        del packet['place_info']
        return packet

    def _add_user_to_chat(self, user_info):
        user_info['host'] = tuple(user_info['host'])
        user_info['id'] = int(user_info['id'])
        host = user_info['host']

        self._peer.connected[host] = user_info
        self._peer.id2host[user_info['id']] = host

        print('[+] Added %s to connected hosts list\n' % str(host))
        print('[*] Now connected hosts are %s\n' % str(self._peer.connected.keys()))

    def _connect_resp(self, rpacket):
        ''' Empty function '''
        return rpacket

    def _new_user(self, rpacket):
        ''' Information about new user in the chat  '''
        closed = { 'parent': [self._peer._parent],
                   'left':   [self._peer._left],
                   'right':  [self._peer._right] }
        side = rpacket['broadcast']['from_node_side']
        user_info = rpacket['broadcast']['user_info']

        self._add_user_to_chat(user_info)

        self._peer.send_broadcast_message(rpacket, closed=closed[side])

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
        packet['connected'] = self._get_connected()

        print('[+] get_chat_info: Created response packet: %s\n' % packet)
        return packet

    def _get_connected(self):
        connected = []
        for host, data in self._peer.connected.items():
            _data = copy.copy(data)
            _data['host'] = host
            connected.append(_data)
        return connected

    def _chat_info(self, rpacket):
        '''
        Process information that we received via get_chat_info request
        '''

        ids = set()
        print('[+] chat_info: Fetched list of connected hosts: {}\n'
              .format(rpacket['connected']))
        for host_data in rpacket['connected']:
            host = tuple(host_data['host'])
            _id = host_data['id']
            username = host_data['username']

            self._peer._add_host(host, { 'id': _id, 'username': username })
            self._peer.id2host[_id] = host

            ids.add(_id)
        if self._peer._id is None:
            own_id = self._peer.generate_id(ids)
            print('[+] Chosen id of current host: %d\n' % own_id)
            self._peer._id = own_id

    def _find_insert_place(self, rpacket, client_id=None, client_host=None,
                           relay=False):
        ''' Find node in the chat's tree for connecting client '''
        if (client_id and client_host) is None:
            client_id = rpacket['from_id']
            client_host = tuple(rpacket['from_host'])
        client = (client_id, client_host)

        # If node position in subtree of current machine
        if self._peer.low_bound < client_id < self._peer.up_bound:
            # if less than current node
            resp = None
            if client_id < self._peer._id:
                resp = self.__process_child('left', rpacket, client, relay)
            else:
                resp = self.__process_child('right', rpacket, client, relay)
            if resp[0]:
                if not relay:
                    del self._peer._opened_connection[tuple(resp[1]['to_host'])]
                return resp if relay else resp[1]
        else:
            # Else in another subtree of parent
            if not relay:
                return self._make_relay(rpacket)
        return (False,) if relay else False

    def __process_child(self, child_side, packet, client, relay=False):
        '''
        Process childs of current node

        Returns:
            (tuple) First place is True if this host contains node for
                    client else False. Second place is info about node place
        '''
        client_id = client[0]
        client_host = client[1]

        if child_side == 'left':
            node = self._peer._left
            neighbor = self._peer._right
            up_bound = self._peer._id
            low_bound = self._peer.low_bound
        else:
            node = self._peer._right
            neighbor = self._peer._left
            up_bound = self._peer.up_bound
            low_bound = self._peer._id

        if node is None:
            place_info = self._form_place(child_side, neighbor,
                                          self._peer._host, up_bound, low_bound)
            packet = self._reverse_packet(packet, TYPES['insert_place'],
                                          relay=relay)
            packet['place_info'] = place_info
            print('[+] Found node location: {} for {}\n'
                  .format(place_info, str(packet['from_host'])))
            return (True, packet)
        else:
            # Else we should relay it
            if not relay:
                return self._make_relay(packet)
        return (False,)

    def _make_relay(self, packet):
        if 'downtype' not in packet:
            packet['downtype'] = packet['type']
        packet['type'] = 'relay'
        packet['client_id'] = packet['from_id']
        packet['client_host'] = packet['from_host']

        return self._relay(packet, first_run=True)

    def _form_place(self, side, neighbor, conn_host, up_bound, low_bound):
        return { 'side': side,
                 'neighbor': neighbor,
                 'conn_host': conn_host,
                 'up_bound': up_bound,
                 'low_bound': low_bound }

    def _reverse_packet(self, packet, _type, relay=False):
        to_id = packet['to_id']
        to_host = packet['to_host']
        if relay:
            packet['type'] = 'relay'
            packet['downtype'] = _type
        else:
            packet['type'] = _type

        packet['to_id'], packet['to_host'] = packet['from_id'], packet['from_host']
        packet['from_id'], packet['from_host'] = to_id, to_host

        return packet

    def _insert_place(self, rpacket):
        ''' Process insert_place response '''
        place_info = rpacket['place_info']
        self._peer._place_info = place_info

        parent = tuple(place_info['conn_host'])

        self._peer.up_bound = place_info['up_bound']
        self._peer.low_bound = place_info['low_bound']
        self._peer._side = place_info['side']
        self._peer._neighbor = place_info['neighbor']
        self._peer._parent = self._peer.connected[parent]['id']

        # return rpacket


    def _relay(self, rpacket, first_run=False):
        '''
        Relay message to the right direction
        '''

        if not first_run and rpacket['downtype'] == 'find_insert_place':
            check_packet = copy.copy(rpacket)
            check_packet['type'] = check_packet['downtype']
            del check_packet['downtype']

            resp = self._find_insert_place(rpacket, rpacket['client_id'],
                                           rpacket['client_host'], relay=True)
            # If current machine have node position for asking client
            if resp[0]:
                return resp[1]

        # If receiver is found
        if not first_run and tuple(rpacket['to_host']) == self._peer._host:
            rpacket['type'] = rpacket['downtype']
            del rpacket['downtype']
            if rpacket['type'] == 'insert_place':
                return self._insert_place_server_proc(rpacket)
            else:
                # TODO Not sure this will work
                return self._table[rpacket['type']].handle(rpacket)

        from_id = rpacket['from_id']
        host = None
        # Receiver in our subtree
        if self._peer.low_bound < from_id < self._peer.up_bound:
            if from_id < self._peer._id:
                host_id = self._peer._left
            else:
                host_id = self._peer._right
        else:
            host_id = self._peer._parent
        host = self._peer.id2host[host_id]

        rpacket['from_host'] = self._peer._host
        rpacket['from_id'] = self._peer._id
        rpacket['to_host'] = host
        rpacket['to_id'] = host_id

        print('[*] Relaying packet {} to {}\n'
              .format(rpacket, rpacket['to_host']))
        self._peer.send_message(host, rpacket)
        return (None,)

    def _insert_place_server_proc(self, rpacket):
        tmp = [['from_id', 'from_host'], ['to_id', 'to_host'],
               ['client_id', 'client_host']]
        for field in range(2):
            for _set in range(len(tmp) - 1):
                rpacket[tmp[_set][field]] = rpacket[tmp[_set + 1][field]]
        for _ in range(2):
            del rpacket[tmp[-1][_]]
        host = tuple(rpacket['to_host'])
        sock = self._peer._send_temp_message(host, rpacket)
        self._peer._inputs.remove(sock)
        sock.close()
        del self._peer._opened_connection[host]


class Handle:
    def __init__(self, proc_func):
        self._proc_func = proc_func

    def handle(self, packet):
        return self._proc_func(packet)
