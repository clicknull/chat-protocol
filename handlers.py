'''
Module contains two classes of handlers. In Handlers class
is placed all handling functionality. Handle class is additional
'''


class Handlers:
    def __init__(self, peer):
        self._peer = peer
        self.create_table()

    def _create_table(self):
        self._table = {
            'connect': Handle(self._connect),
            'disconnect': Handle(self._disconnect),
            'ping': Handle(self._ping),
            'get_chat_info': Handle(self._get_chat_info),
            'chat_info': Handle(self._chat_info),
            'relay': Handle(self._relay)
        }

    def _connect(self):
        pass

    def _disconnect(self):
        pass

    def _ping(self):
        pass

    def _get_chat_info(self):
        '''
        If packet's type is 'get_chat_info' then new user want to
        fetch information about chat. In this case we should send it to
        him
        '''

        packet = self._peer._create_packet(_type='chat_info')

    def _chat_info(self):
        pass

    def _relay(self):
        pass


class Handle:
    def __init__(self, proc_func):
        self._proc_func = proc_func

    def handle(packet):
        self._proc_func(packet)
