"""
Utilities for authentication
"""

import getpass
from paramiko.agent import Agent
from paramiko.ssh_exception import AuthenticationException, BadAuthenticationType, ChannelException, SSHException

def interpret_urlish(url: str):
    """
    Interpret the server urlishes (so-called due to their non-conformance with traditional urls)

    Formatted like this:

    [username@]some.server.with.a.dns.name:some/path/yipee

    Returns an array of [username (defaults to logged in user), servername, path]
    """

    if "@" in url and url.index("@") < url.index(":"):
        username, *url = url.split("@")
        url = "".join(url)
    else:
        username = getpass.getuser()

    servername, *url = url.split(":")
    path = "".join(url)

    return [username, servername, path]

use_public_key  = True  # if true, try to use public key first, if false only try if password fails
use_password    = True  # if true, use the password, if false don't bother
use_interactive = True  # if true and all else fails, fallback to interactive mode

guessed_username = ""
guessed_password = ""

def interpret_authentication_params(urlish, username, password, no_interactive):
    """
    Interpret parameters passed in to guess authentication parameters. Any can be none.

    If no method works, fall back to interactive auth
    """
    global use_password, use_interactive, use_interactive, guessed_username, guessed_password

    if urlish and not username:
        guessed_username, *_ = interpret_urlish(urlish)
    elif username:
        guessed_username = username
    else:
        guessed_username = getpass.getuser()

    if password:
        use_public_key = False
        guessed_password = password
    else:
        use_password = False

    if no_interactive:
        use_interactive = False


def authenticate_transport(transport):
    """
    Authenticate the transport with the current authentication parameters.

    Raises AuthenticationException if the authentication failed
    """
    global use_public_key, use_password, use_interactive, guessed_password

    if use_password and not use_public_key:
        try:
            transport.auth_password(guessed_username, guessed_password)
        except ( BadAuthenticationType, AuthenticationException ):
            use_password = False

    if transport.is_authenticated():
        return

    if use_public_key or not use_password:
        agent = Agent()
        keys = agent.get_keys()
        if keys:
            key = keys[0]

            try:
                transport.auth_publickey(guessed_username, key)
            except ( BadAuthenticationType, AuthenticationException ):
                use_public_key = False
            finally:
                agent.close()
        else:
            use_public_key = False
            agent.close()
 
    if transport.is_authenticated():
        return

    if use_interactive:
        def interactive_handler(title, instruct, prompts):
            return [input(x) if y else getpass.getpass(x) for x, y in prompts]

        try:
            transport.auth_interactive(guessed_username, interactive_handler)
        except BadAuthenticationType:
            guessed_password = getpass.getpass("Password: ")
            transport.auth_password(guessed_username, guessed_password)
            use_password = True
    
    if transport.is_authenticated():
        return

    raise AuthenticationException("could not authenticate with any of the methods")
