"""
Contains the Repository class, the main way to interact with a configfiles repo

Internally, repositories are stored as a folder with the following structure

(repo root)
|
=- index.json
=- scripts/
  =- (hash).py
  =- (hash2).py
  ...
=- locks/
  =- write_lock
  =- read_lock_0  (auto incremented using listdir)

index.json contains various information, such as script names and sources (often auto-generated)
scripts/ contains all of the scripts, named by their sha1 hashes
locks/ contains the lockfiles.

write_lock's presence indicates another configfiles instance is writing or modifying the repo and no reads nor changes should occur
read_lock's presence indicates another configfiles instance is reading the data, so no modification may occur.
Other reads can occur just fine, with autoincreasing numbers to be unique

The repository's index contains a few fields:

- version: currently 1, following fields are for this version
- scripts: dictionary of script objects
- start: start of script objects
- revision: increments with every additional script
- end

so:

- name
- files: list of files modified by the script (filenames)
- next: next script in chain
- prev: previous script in chain
"""

from socket import socket
from paramiko.transport import Transport
from .locks import RepoReadLock, RepoWriteLock
from ..auth import authenticate_transport, interpret_urlish
from hashlib import sha512
import json

class Repository:
    def __init__(self, url):
        self.url = url
        self.index = {}

        self.read_lock = RepoReadLock(url)
        self.write_lock = RepoWriteLock(url)

        self.client = None
        self.transport = None
        self.socket = socket()

        self.opened = False

    def open(self):
        """
        Opens the connection
        """

        self.socket.connect((interpret_urlish(self.url)[1], 22))
        self.transport = Transport(self.socket)
        self.transport.start_client()
        authenticate_transport(self.transport)
        self.client = self.transport.open_sftp_client()
        target_path = interpret_urlish(self.url)[2]
        try:
            self.client.stat(target_path)
        except IOError:
            self.client.mkdir(target_path)
        self.client.chdir(target_path)
        self.opened = True

    def close(self):
        """
        Closes the connection
        """

        if not self.opened:
            return
        self.client.close()
        self.transport.close()
        self.socket.close()
        self.opened = False

    def update(self):
        """
        Update the information in this class to match that of the remote.

        Raises exceptions if remote is invalid or in an invalid state
        """

        if not self.opened:
            self.open()

        with self.read_lock:
            with self.client.open("index.json") as f:
                self.index = json.load(f)

    def get_script(self, hname=None):
        """
        Get the script object
        """
        if hname is None:
            hname = self.index["start"]
        return self.index["scripts"][hname]

    def download_script(self, hname=None):
        if hname is None:
            hname = self.index["start"]
        with self.read_lock:
            with self.client.open("scripts/" + hname + ".py", "r") as f:
                return f.read()

    def get_revision(self):
        return self.index["revision"]

    def append_script(self, script_obj, script_contents):
        h = sha512()
        h.update(script_contents.encode("utf-7"))
        hname = h.hexdigest()
        script_obj["prev"] = self.index["end"]

        with self.write_lock:
            self.index["revision"] += 1
            if self.index["end"]: self.index["scripts"][self.index["end"]]["next"] = hname
            self.index["end"] = hname
            self.index["scripts"][hname] = script_obj

            if self.index["start"] == "":
                self.index["start"] = hname

            self._write()
            with self.client.open("scripts/" + hname + ".py", "w") as f:
                f.write(script_contents)

    def _write(self):
        with self.client.open("index.json", "w") as f:
            json.dump(self.index, f)

    def write(self):
        with self.write_lock:
            self._write()

    def __iter__(self):
        return FollowChainIterator(self, self.index["start"])

    def iterate_from(self, pos):
        return FollowChainIterator(self, pos)

    def new(self):
        if not self.opened:
            self.open()

        try:
            self.client.stat("index.json")
            raise RuntimeError("already init-ed, manually delete the folder to re-init")
        except IOError:
            pass

        # create the skeleton fs
        self.client.mkdir("locks")
        self.client.mkdir("scripts")

        # create a basic index.json
        self.index = {
                "version": 1,
                "revision": 0,
                "start": "",
                "end": "",
                "scripts": {}
        }

        self.write()



class FollowChainIterator:
    def __init__(self, repo, start):
        self.repo = repo
        self.pos = start

    def __next__(self):
        if not self.pos:
            raise StopIteration
        n = self.pos
        result = self.repo.get_script(self.pos)
        self.pos = result["next"]
        return n

    def __iter__(self):
        return self
