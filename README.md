# CloudFlare Dynamic DNS client

This is a simple Dynamic DNS script written in Python for updating CloudFlare DNS A records,  
similar to the classic [ddclient perl script](https://sourceforge.net/p/ddclient/wiki/Home/).

- You can run it as a cron job or a systemd timer.
- It only updates the records if the IP address actually changed by storing a
  cache of the current IP address.
- It checks multiple IP services. If one of them doesn't respond, it skips it and check the next.
- It has an easy to use command line interface.

## Install

The simplest way to run this script is using the `uv` Python package manager:

```bash
$ uvx cloudflare-dyndns
```

You can install it with pip [from PyPI](https://pypi.org/project/cloudflare-dyndns/):

```bash
$ pip install cloudflare-dyndns
```

There is a Nix package available as well:
```bash
nix-shell -p cloudflare-dyndns
```
Or you can even configure NixOS to use it as a service by setting `services.cloudflare-dyndns` options in `configuration.nix`.  
See `man 5 configuration.nix` on NixOS for details.


You can use [the Docker image](https://hub.docker.com/r/kissgyorgy/cloudflare-dyndns):
```bash
$ docker run --rm -it kissgyorgy/cloudflare-dyndns --help
```

Please note that before you can use the `-6` IPv6 option in Docker, you need to [enable IPv6 support in the Docker daemon](https://docs.docker.com/config/daemon/ipv6/).
Afterward, you can choose to use either IPv4 or IPv6 (or both) with any container, service, or network.

# Note

If you use this script, it "takes over" the handling of the record of those
domains you specified, which means it will update existing records and create
missing ones.

You should not change A or AAAA records manually or with other scripts, because
the changes will be overwritten.

I decided to make it work this way, because I think most users expect this
behavior, but if you have a different use case,
[let me know!](https://github.com/kissgyorgy/cloudflare-dyndns/issues/new)

## Command line interface

<!-- ```$
echo "$ cloudflare-dyndns --help"
cloudflare-dyndns --help
``` -->

```
$ cloudflare-dyndns --help
Usage: cloudflare-dyndns [OPTIONS] [DOMAINS]...

  A command line script to update CloudFlare DNS A and/or AAAA records based
  on the current IP address(es) of the machine running the script.

  For the main domain (the "@" record), simply put "example.com".
  Subdomains can also be specified, eg. "*.example.com" or "sub.example.com"

  You can set the list of domains to update in the CLOUDFLARE_DOMAINS
  environment variable, in which the domains has to be separated by
  whitespace, so don't forget to quote the value!

  The script supports both IPv4 and IPv6 addresses. The default is to set only
  A records for IPv4, which you can change with the relevant options.

Options:
  --api-token TEXT       CloudFlare API Token (You can create one at My
                         Profile page / API Tokens tab). Can be set with
                         CLOUDFLARE_API_TOKEN environment variable. Mutually
                         exclusive with `--api-token-file`.
  --api-token-file FILE  File containing CloudFlare API Token (You can create
                         one at My Profile page / API Tokens tab). Can be set
                         with CLOUDFLARE_API_TOKEN_FILE environment variable.
                         Mutually exclusive with `--api-token`.
  --verify-token         Check if the API token is valid through the
                         CloudFlare API.
  --proxied              Whether the records are receiving the performance and
                         security benefits of Cloudflare.
  -4 / -no-4             Turn on/off IPv4 detection and set A records.
                         [default: on]
  -6 / -no-6             Turn on/off IPv6 detection and set AAAA records.
                         [default: off]
  --delete-missing       Delete DNS record when no IP address found. Delete A
                         record when IPv4 is missing, AAAA record when IPv6 is
                         missing.
  --cache-file FILE      Cache file  [default: (~/.cache/cloudflare-
                         dyndns/ip.cache)]
  --force                Delete cache and update every domain
  --debug                More verbose messages and Exception tracebacks
  --version              Show the version and exit.
  --help                 Show this message and exit.
```

## Shell exit codes

- `1`: Unknown error happened
- `2`: IP cannot be determined (IP service error)
- `3`: CloudFlare related error (cannot call API, cannot get records, etc...)


## Changelog

See the [Releases page](https://github.com/kissgyorgy/cloudflare-dyndns/releases) for a full Changelog.


## Development

The development is done with devenv (https://devenv.sh), you don't need anything
else, just install devenv and run `devenv shell` and you are good to go.

Run `uv sync` to install dependencies or `pytest` to run the tests.
