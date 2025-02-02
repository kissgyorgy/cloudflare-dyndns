version := `project-version`
binary-name := "cloudflare-dyndns-linux-x86-" + version
sha256-name := binary-name + ".sha256"
docker-image := "kissgyorgy/cloudflare-dyndns"
docker-image-latest := docker-image + ":latest"
docker-image-version := docker-image + ":" + version

help:
    @just --list

clean:
    rm -r build/ dist/ {{ binary-name }} {{ sha256-name }}

print-version:
    @echo Current version: v{{ version }}

build-package: print-version
    uv build

build-docker: print-version
    docker build -t {{ docker-image-version }} .
    docker tag {{ docker-image-version }} {{ docker-image-latest }}

build-all: build-package build-docker

release-docker: build-docker
    docker push {{ docker-image-version }}
    docker push {{ docker-image-latest }}

release-python: build-package
    #!/usr/bin/env bash
    export UV_PUBLISH_TOKEN=$(op.exe read op://Secrets/pypi-token/credential)
    FILES=$(find dist -regextype posix-extended -regex 'dist/cloudflare_dyndns-5\.1(\.tar\.gz|.*\.whl)')
    uv publish $FILES

release-github: print-version
    git tag {{ version }}
    git push origin --tags

release-all: release-docker release-python release-github

test:
    pytest

check:
    pre-commit run --all-files --hook-stage manual
