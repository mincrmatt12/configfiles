"""
Contains functions to get hashed names for things
"""

from hashlib import sha512
from ..auth import interpret_urlish

def get_remote_hash(remote):
    m = sha512()
    _, server, path = interpret_urlish(remote)
    path = path.rstrip("/").rstrip()
    server = server.rstrip()
    m.update(server.encode("utf-8"))
    m.update(path.encode("utf-8"))
    return m.hexdigest()

def get_file_hash(remotehash, filename, scripthash):
    """
    Get the file hash

    :param filename: the name of the file
    :param remotehash: the remote hash
    :param scripthash: the script hash
    """

    m = sha512()
    m.update(remotehash.encode("utf-8"))
    m.update(filename.encode("utf-8"))
    m.update(scripthash.encode("utf-8"))
    return m.hexdigest()
