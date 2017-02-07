import argparse


class Parser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__()
        self.create_parser()

    def create_parser(self):
        self.add_argument(
            "-a", "--address", dest="ip", type=str, help="Set ip"
        )
        self.add_argument(
            "-p", "--port", dest="port", type=str, help="Set port"
        )
