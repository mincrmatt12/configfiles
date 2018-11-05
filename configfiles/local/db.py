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
import sys
from ..repo import Repository
from .hashes import get_remote_hash
import tempfile
import subprocess
import click

class DotConfigFiles:
    def __init__(self, load_file="~/.configfiles", remote=None):
        self.load_file = os.path.expanduser(load_file)
        if not os.path.exists(self.load_file) or not os.path.isdir(self.load_file):
            os.makedirs(self.load_file)
        if not os.path.exists(os.path.join(self.load_file, "files")):
            os.makedirs(os.path.join(self.load_file, "files"))

        index_path = os.path.join(self.load_file, "current")
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                self.current_remote = f.read()
        elif remote is not None:
            self.current_remote = get_remote_hash(remote)
        else:
            raise ValueError("no existing file, i need the remote")
        self._try_load(remote)

        self.filemon = FileMon(self)

    def _try_load(self, remote):
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

        for fname in self.index["files"]:
            self.filemon.restore_version(fname, None)

        self.index["at"] = ""
        self.index["revision"] = -1
        self.write()

    def rollback(self, count=1):
        """
        Rolls back the repo. To do this remotely or permanently, create an undo script (or copy the target file and do a re-sync)
        """

        self.repo.update()

        # Get the previous script ID.
        previous_script = self.get_at()
        if previous_script == "":
            self.desync() # rolling back to original == desync
            return
        for i in range(count):
            previous_script = self.repo.get_script(previous_script)["prev"]
            if previous_script == "":
                self.desync() # rolling back to original == desync
                return

        # Restore all files to their state right now.
        for fname in self.index["files"]:
            self.filemon.restore_version(fname, previous_script)

        self.index["at"] = previous_script
        self.index["revision"] = -1
        self.write()

        click.echo("rolled back to " + previous_script)

    def sync(self, fastforward=True, remote=None):
        """
        Syncs the repo
        """

        if remote != None and get_remote_hash(remote) != self.current_remote:
            # Do a sanity check; is the repo desynced?
            if self.index["at"] != "":
                raise RuntimeError("desync the repo first")
            else:
                self.repo.close()
                fastforward = False
                self._try_load(remote)
        else:
            remote = self.index["remote"]

        if self.up_to_date():
            return

        if self.repo.index["end"] == "":
            click.echo("nothing in repo, nothing to do")
            self.current_remote = get_remote_hash(remote)
            with open(os.path.join(self.load_file, "current"), "w") as f:
                f.write(self.current_remote)

            self.write()
            return

        # Sync the repo
        self.repo.update()

        # First, check if we can fastforward.
        if fastforward:
            current_script = self.repo.get_script(self.repo.index["end"])
            if all([
                (x in self.index["files"] and self.repo.index["end"] in self.index["files"][x]["chain"]) for x in current_script["files"] 
            ]):
                click.echo("fastforwarding to " + self.repo.index["end"])

                for x in current_script["files"]:
                    self.filemon.restore_version(x, self.repo.index["end"])

                self.index["at"] = self.repo.index["end"]
                self.write()

                return

        script_path = os.path.join(self.load_file, "script.py")
        script_path = os.path.abspath(script_path)

        # Main loop; while not fully synced (not fastforward)
        while self.get_at() != self.repo.index["end"]:
            if self.get_at() != "":
                next_script = self.repo.get_script(self.get_at())["next"]
                so = self.repo.get_script(next_script)
            else:
                next_script = self.repo.index["start"]
                so = self.repo.get_script(next_script)

            # For each file, check if it needs originalizing
            for x in so["files"]:
                if x not in self.index["files"] or self.index["files"][x]["newin"] == next_script:
                    # record original
                    self.filemon.record_original(x, next_script)

            # Apply the script.
            script_code = self.repo.download_script(next_script)
            with open(script_path, "w") as f:
                f.write(script_code.decode("utf-8"))
            
            click.echo("running " + so["name"])
            
            result = subprocess.run([sys.executable, os.path.relpath(script_path, os.path.dirname(self.load_file))], cwd=os.path.dirname(self.load_file))
            self.index["at"] = next_script
            if result.returncode != 0:
                click.echo("err: one of the scripts failed.")
                self.rollback()
                return

            # Record post-files
            for x in so["files"]:
                self.filemon.record_file(x)

        self.current_remote = get_remote_hash(remote)
        with open(os.path.join(self.load_file, "current"), "w") as f:
            f.write(self.current_remote)

        self.index["revision"] = self.repo.get_revision()
        self.write()
        click.echo("synced to " + self.index["remote"])

    def append(self, script_text, name, files, runnow=False):
        script_obj = {
                "name": name,
                "files": files,
                "next": ""
        }

        self.repo.update()
        self.repo.append_script(script_obj, script_text)

        if runnow:
            self.sync()

from .filemon import FileMon
