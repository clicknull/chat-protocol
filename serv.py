import socket

from bst_peer import BinaryTreePeer


def main():
    peer_server = BinaryTreePeer(9090)

    peer_server.start()


if __name__ == '__main__':
    main()
