"""
Contains the .configfiles database object.

The .configfiles stores the following information:

index.json:

    - revision (current revision)
    - at (current script index)
    - files (file tracking information database)
    - remote (remote urlish)

files:

    "name": {
        "chain": {"fhash": "statename"},
    }

files folder:

statename list

"""

import json
import os
from ..repo import Repository

class DotConfigFiles:
    def __init__(self, load_file="~/.configfiles", remote=None):
        load_file = os.path.expanduser(load_file)
        if not os.path.exists(load_file) or not os.path.isdir(load_file):
            raise RuntimeError("target path does not exist")

        index_path = os.path.join(load_file, "index.json")
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                self.index = json.load(f)
        else:
            self.repo = Repository
            self.index = {
                    "revision": -1,
                    "at":
            }
