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

Or you can use [the Docker image](https://hub.docker.com/r/kissgyorgy/cloudflare-dyndns):

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

```
$ cloudflare-dyndns --help
Usage: cloudflare-dyndns [OPTIONS] [DOMAINS]...

  A command line script to update CloudFlare DNS A and/or AAAA records based
  on the current IP address(es) of the machine running the script.

  For the main domain (the "@" record), simply put "example.com"
  Subdomains can also be specified, eg. "*.example.com" or "sub.example.com"

  You can set the list of domains to update in the CLOUDFLARE_DOMAINS
  environment variable, in which the domains has to be separated by
  whitespace, so don't forget to quote the value!

  The script supports both IPv4 and IPv6 addresses. The default is to set
  only A records for IPv4, which you can change with the relevant options.

Options:
  --api-token TEXT   CloudFlare API Token (You can create one at My Profile
                     page / API Tokens tab). Can be set with
                     CLOUDFLARE_API_TOKEN environment variable.  [required]

  --proxied          Whether the records are receiving the performance and
                     security benefits of Cloudflare.

  -4 / -no-4         Turn on/off IPv4 detection and set A records.
                     [default: on]

  -6 / -no-6         Turn on/off IPv6 detection and set AAAA records.
                     [default: off]

  --delete-missing   Delete DNS record when no IP address found. Delete A
                     record when IPv4 is missing, AAAA record when IPv6 is
                     missing.

  --cache-file FILE  Cache file  [default: /home/walkman/.cache/cloudflare-
                     dyndns/ip.cache]

  --force            Delete cache and update every domain
  --debug            More verbose messages and Exception tracebacks
  --help             Show this message and exit.
```

## Shell exit codes

- `1`: Unknown error happened
- `2`: IP cannot be determined (IP service error)
- `3`: CloudFlare related error (cannot call API, cannot get records, etc...)

# Changelog

- **v5.0** Mac OS Support

  Able to read CA bundle from trust stores on Mac OS too, no need for file-based CA store.

- **v4.0** IPv6 support

  Now you can specify `-6` command line option to update AAAA records too.  
  You can delete records for missing IP addresses with the `--delete-missing`
  option. See [issue #6](https://github.com/kissgyorgy/cloudflare-dyndns/issues/6) for details.  
  There is a new `--proxied` flag for setting Cloudflare DNS services.

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
