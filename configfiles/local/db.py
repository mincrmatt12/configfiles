"""
Contains the .configfiles database object.

The .configfiles stores the following information:

current - text file containing remote hash.

rhash = urlish 1+2 with trailing / removed

(remotehash).json:

    - revision (current revision)
    - at (current script index)
    - files (file tracking information database)
    - remote (remote urlish)

files:

    "name": {
        "chain": {"fhash": "statename"},
        "newin": "hash",
        "original": "statehash"
    }

files folder:

statename.gz (gzipped file)

"""

import json
import os
from ..repo import Repository
from .hashes import get_remote_hash
from .filemon import FileMon

class DotConfigFiles:
    def __init__(self, load_file="~/.configfiles", remote=None):
        self.load_file = os.path.expanduser(self.load_file)
        if not os.path.exists(self.load_file) or not os.path.isdir(self.load_file):
            raise RuntimeError("target path does not exist")

        index_path = os.path.join(self.load_file, "current")
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                self.current_remote = f.read()
        else:
            self.current_remote = get_remote_hash(remote)

        index_path = os.path.join(self.load_file, self.current_remote + ".json")
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                self.index = json.load(f)
            self.repo = Repository(self.index["remote"])
        else:
            self.repo = Repository(remote)
            self.index = {
                    "revision": -1,
                    "at": "",
                    "files": {},
                    "remote": remote
            }

        self.filemon = FileMon(self)

    def restore_original(self, filename):
        """
        Restores the original copy of filename, using the current remote's original copy. (Theoretically this will be the same, but one can never be too sure)
        """

        if filename not in self.index["files"]:
            raise ValueError("file not found in database")

        self.filemon.restore_version(filename, None)

    def get_at(self):
        return self.index["at"]

    def get_revision(self):
        return self.index["revision"]

    def up_to_date(self):
        self.repo.update()
        return self.get_revision() >= self.repo.get_revision()

    def close(self):
        self.repo.close()
        self.write()

    def write(self):
        with open(os.path.join(self.load_file, self.current_remote + ".json"), "w") as f:
            json.dump(self.index, f)

    def desync(self):
        """
        De-syncs the repo. Restores all files to original state, and sets at to ""
        """


