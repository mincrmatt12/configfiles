"""
MAIN CLI INTERFACE
"""

import click
from .local import DotConfigFiles
from .gen import patcher
from .auth import interpret_authentication_params
from .repo import Repository
import os

local_dir = ""
password = None
username = None
no_interactive = None

@click.group()
@click.option('-p', '--password', 'passw', default=None, type=str)
@click.option('-u', '--username', 'user', default=None, type=str)
@click.option('--local', default=None, type=click.Path(writable=True), help="override default db directory, to create localized instances")
@click.option('--interactive/--no-interactive', default=True, help="no interactive auth")
def cli(passw, user, interactive, local):
    global local_dir, password, username, no_interactive
    password, username, no_interactive, local_dir = passw, user, not interactive, local
    if local_dir is None:
        local_dir = "~"

@cli.command()
@click.argument('remote', required=False, default=None)
@click.option('--ff/--no-ff', default=True, help="allow fastforwarding")
@click.option('-c', '--count', required=False, default=-1, type=int, help="amount of times to sync, -1 to latest")
def sync(remote, ff, count):
    interpret_authentication_params(remote, username, password, no_interactive)
    db = DotConfigFiles(load_file=os.path.join(local_dir, ".configfiles"), remote=remote)
    db.sync(fastforward=ff, remote=remote, maxiter=count)
    db.close()

@cli.command()
def desync():
    interpret_authentication_params(None, username, password, no_interactive)
    db = DotConfigFiles(load_file=os.path.join(local_dir, ".configfiles"))
    db.desync()
    db.close()

@cli.command()
@click.option("--apply", default=False, type=bool, help="run the script now")
@click.option("-n", "--name", default=None, type=str, help="script user name")
@click.argument("script", type=click.File())
@click.argument("updates", type=str, nargs=-1)
def add(script, updates, apply, name):
    interpret_authentication_params(None, username, password, no_interactive)
    db = DotConfigFiles(load_file=os.path.join(local_dir, ".configfiles"))
    
    new_update = []
    home_dir = os.path.dirname(db.load_file)
    for f in updates:
        if not os.path.exists(f):
            click.confirm("file {} doesn't exist, add anyways? ".format(f))
            new_update.append(f)
        else:
            ab = os.path.abspath(f)
            new_update.append(os.path.relpath(ab, start=home_dir))
            click.echo("modifies {}".format(new_update[-1]))

    with script as f:
        script_text = f.read()

    if name is None:
        name = "custom script {}".format(script.name)

    db.append(script_text, name, new_update, runnow=apply)
    db.close()

@cli.command()
@click.argument("names", type=click.Path(exists=True, dir_okay=False), nargs=-1, required=True)
@click.option("-n", "--name", default=None, type=str, help="script user name")
def update(names, name):
    interpret_authentication_params(None, username, password, no_interactive)
    db = DotConfigFiles(load_file=os.path.join(local_dir, ".configfiles"))

    writes = []
    patches = []

    home_dir = os.path.dirname(db.load_file)
    for f in names:
        ab = os.path.abspath(f)
        rel = os.path.relpath(ab, start=home_dir)

        if rel.rstrip("/") in db.index["files"]:
            patches.append(rel)
        else:
            writes.append(rel)

    if writes:
        if name is None:
            wname = "create {0}".format(", ".join(writes))
        else:
            wname = name

        script_text = patcher.create_template_write(db, writes)
        db.append(script_text, wname, writes)
    if patches:
        if name is None:
            wname = "update {0}".format(", ".join(patches))
        else:
            wname = name

        script_text = patcher.create_template_update(db, patches)
        db.append(script_text, wname, patches)

    click.echo("created scripts")
    db.close()


@cli.command()
@click.argument("remote", type=str)
def init(remote):
    interpret_authentication_params(remote, username, password, no_interactive)
    
    repo = Repository(remote)
    repo.open()
    repo.new()
    repo.close()

    print("create blank configfiles repo at {}".format(remote))

@cli.command()
@click.argument("times", type=int, default=1)
def rollback(times):
    interpret_authentication_params(None, username, password, no_interactive)
    db = DotConfigFiles(load_file=os.path.join(local_dir, ".configfiles"))
    db.rollback(times)

if __name__ == "__main__":
    cli()
