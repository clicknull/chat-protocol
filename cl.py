from bst_peer import BinaryTreePeer


def main():
    peer = BinaryTreePeer(9090, ('localhost', 9091))
    peer.start()

if __name__ == '__main__':
    main()