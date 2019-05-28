# CloudFlare Dynamic DNS client

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
