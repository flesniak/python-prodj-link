import unittest
from unittest.mock import Mock, patch
import socket

from prodj.network.nfsclient import NfsClient
from prodj.network.packets_nfs import RpcMsg

class MockSock(Mock):
    def __init__(self, inet, type):
        assert inet == socket.AF_INET
        assert type == socket.SOCK_DGRAM
        self.sent = list()

    def sendto(self, data, host):
        msg = RpcMsg.parse(data)
        self.sent += msg
        print(msg)

class DbclientTestCase(unittest.TestCase):
    def setUp(self):
        self.nc = NfsClient(None) # prodj object only required for enqueue_download_from_mount_info
        # TODO: use unittest.mock for replacing socket module
        # self.sock = MockSock
        # NfsClient.socket.socket = self.sock

        # assert self.sock.binto.called

    @patch('socket.socket', new=MockSock)
    @patch('prodj.network.nfsclient.select')
    def test_buffer_download(self, select):
        self.nc.enqueue_buffer_download("1.1.1.1", "usb", "/folder/file")
