"""
Implements the locking functionality of repositories
"""

from paramiko.transport import Transport
from ..auth import authenticate_transport, interpret_urlish
from socket import socket

class RepoReadLock:
    def __init__(self, url):
        self.url = url
        self.transport = None
        self.client = None
        self.socket = None
        self.i = 0

    def __enter__(self):
        self.socket = socket()
        self.socket.connect((interpret_urlish(self.url)[1], 22))
        self.transport = Transport(self.socket)
        self.transport.start_client()
        authenticate_transport(self.transport)
        self.client = self.transport.open_sftp_client()
        self.client.chdir(interpret_urlish(self.url)[2])

        self._lock()

    def _lock(self):
        target_locks = self.client.listdir("locks")
        target_locks.sort()

        if "write_lock" in target_locks:
            raise RuntimeError("repo is write locked; try again later")
        else:
            self.i = 0
            while "read_lock_" + str(self.i) in target_locks:
                self.i += 1
            self.client.mkdir("locks/read_lock_" + str(self.i))

    def _unlock(self):
        self.client.rmdir("locks/read_lock_" + str(self.i))

    def __exit__(self, *args):
        self._unlock()

        self.client.close()
        self.transport.close()
        self.socket.close()

class RepoWriteLock:
    def __init__(self, url):
        self.url = url
        self.transport = None
        self.client = None
        self.socket = socket()

    def __enter__(self):
        self.socket.connect((interpret_urlish(self.url)[1], 22))
        self.transport = Transport(self.socket)
        self.transport.start_client()
        authenticate_transport(self.transport)
        self.client = self.transport.open_sftp_client()
        self.client.chdir(interpret_urlish(self.url)[2])

        self._lock()

    def _lock(self):
        target_locks = self.client.listdir("locks")
        target_locks.sort()

        if target_locks:
            raise RuntimeError("repo is locked; try again later")
        else:
            self.client.mkdir("locks/write_lock")

    def _unlock(self):
        self.client.rmdir("locks/write_lock")

    def __exit__(self, *args):
        self._unlock()

        self.client.close()
        self.transport.close()
        self.socket.close()
