import cmd
import sys
from arg_parser import Parser
from sock_wrapper import Client, Server


class Cli(cmd.Cmd):
    def __init__(self, options):
        super().__init__()
        self.prompt = "Enter your message: "
        self.opt = options
        self.server = Server('192.168.1.6', 12345)
        self.client = Client('192.168.1.3', 12345)

    def default(self, line):
        self.client.my_send(line)

    def do_exit(self, args):
        self.client._handle_recv_data = False
        self.server._handle_recv_data = False
        sys.exit(0)


if __name__ == "__main__":
    parser = Parser()
    Cli(parser.parse_args()).cmdloop()
