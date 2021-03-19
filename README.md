# CloudFlare Dynamic DNS client

This is a simple Dynamic DNS script written in Python for updating CloudFlare DNS A records,  
similar to the classic [ddclient perl script](https://sourceforge.net/p/ddclient/wiki/Home/).

- You can run it as a cron job or a systemd timer.
- It only updates the records if the IP address actually changed by storing a
  cache of the current IP address.
- It checks multiple IP services. If one of them doesn't respond, it skips it and check the next.
- It has an easy to use command line interface.

## Install

You can simply install it with pip [from PyPI](https://pypi.org/project/cloudflare-dyndns/):

```bash
$ pip install cloudflare-dyndns
```

Or you can [download a standalone binary from the releases page.](https://github.com/kissgyorgy/cloudflare-dyndns/releases/)

Or you can use [the Docker image](https://hub.docker.com/repository/docker/kissgyorgy/cloudflare-dyndns):

```bash
$ docker run --rm -it kissgyorgy/cloudflare-dyndns --help
```

## Command line interface

```
$ cloudflare-dyndns --help
Usage: cloudflare-dyndns [OPTIONS] [DOMAINS]...

  A simple command line script to update CloudFlare DNS A records with the
  current IP address of the machine running the script.

  For the main domain (the "@" record), simply put "example.com"
  Subdomains can also be specified, eg. "*.example.com" or "sub.example.com"

  You can set the list of domains to update in the CLOUDFLARE_DOMAINS
  environment variable, in which the domains has to be separated by
  whitespace, so don't forget to quote the value!

Options:
  --api-token TEXT   CloudFlare API Token (You can create one at My Profile
                     page / API Tokens tab). Can be set with
                     CLOUDFLARE_API_TOKEN environment variable.  [required]

  --cache-file FILE  Cache file  [default: ~/.cache/cloudflare-dynds/ip.cache]
  --force            Delete cache and update every domain
  --debug            More verbose messages and Exception tracebacks
  --help             Show this message and exit.
```

# Changelog

- **v3.0** breaks backward compatibility using the global API Key

  You can only use API Tokens now, which you can create under `My Profile / API Tokens`: https://dash.cloudflare.com/profile/api-tokens.
  The problem with the previously used API Key is that it has global access to
  your Cloudflare account. With the new API Tokens, you can make the script
  permissions as narrow as needed.

  **Upgrading from 2.0 and using API Tokens is highly recommended!**

  The `--domains` option is now gone, because it made no sense (it only existed
  for reading from the envvar), but you can use the `CLOUDFLARE_DOMAINS` envvar
  the same as before.

- **v2.0** breaks backward compatibility for a PyPI release.

  The script you need to run is now called `cloudflare-dyndns` and the cache file
  also changed. You can delete the old cache manually, or you can leave it, it
  won't cause a problem.

  The Docker file entry point is changed, so if you pull the new image, everything
  will work as before.

## Development

You can install dependencies with poetry (preferable in a virtualenv).  
After [installing poetry](https://poetry.eustace.io/docs/#installation), simply run:

```bash
$ poetry install
```
