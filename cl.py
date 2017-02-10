from bst_peer import BinaryTreePeer


def main():
    peer = BinaryTreePeer(9091, ('localhost', 9090))

    peer.start()


if __name__ == '__main__':
    main()
