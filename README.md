# CloudFlare Dynamic DNS client

This is a simple Dynamic DNS script written in Python for updating CloudFlare DNS A records,  
similar to the classic [ddclient perl script](https://sourceforge.net/p/ddclient/wiki/Home/).

- You can run it as a cron job or a systemd timer.
- It only updates the records if the IP address actually changed by storing a
  cache of the current IP address.
- It checks multiple IP services. If one of them doesn't respond, it skips it and check the next.
- It has an easy to use command line interface.


## Install
You can install dependencies with poetry (preferable in a virtualenv).  
After [installing poetry](https://poetry.eustace.io/docs/#installation), simply run:  
```bash
$ poetry install
```


## Command line interface

```bash
$ cfdns.py --help
Usage: cfdns.py [OPTIONS] DOMAINS...

  A simple command line script to update CloudFlare DNS A records with the
  current IP address of the machine running the script.

  For the main domain (the "@" record), simply put "example.com"
  Subdomains can also be specified, eg. "*.example.com" or "sub.example.com"

Options:
  --email TEXT       CloudFlare account email. Can be set with
                     CLOUDFLARE_EMAIL environment variable  [required]
  --api-key TEXT     CloudFlare API key (You can find it at My Profile page).
                     Can be set with CLOUDFLARE_API_KEY environment variable.
                     [required]
  --cache-file FILE  Cache file  [default: ~/.cache/cfdns/cfdns.cache]
  --force            Delete cache and update every domain
  --debug            More verbose messages and Exception tracebacks
  --help             Show this message and exit.
```
