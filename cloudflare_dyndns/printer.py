import functools

import click

success = functools.partial(click.secho, fg="green")
warning = functools.partial(click.secho, fg="yellow")
error = functools.partial(click.secho, fg="red")
info = click.echo
