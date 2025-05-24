version := `project-version`
binary-name := "cloudflare-dyndns-linux-x86-" + version
sha256-name := binary-name + ".sha256"
docker-image := "kissgyorgy/cloudflare-dyndns"
docker-image-latest := docker-image + ":latest"
docker-image-version := docker-image + ":" + version

help:
    @just --list

clean:
    rm -rf build/ dist/ {{ binary-name }} {{ sha256-name }} \
        .devenv/* .devenv.* .direnv/* .pytest_cache/* .ruff_cache .pre-commit-config.yaml
    find -name "*.pyc" -delete

print-version:
    @echo Current version: {{ version }}

build-package: print-version
    uv build

build-docker: print-version
    docker build -t {{ docker-image-version }} .
    docker tag {{ docker-image-version }} {{ docker-image-latest }}

build-all: build-package build-docker

release-docker: check test build-docker
    docker push {{ docker-image-version }}
    docker push {{ docker-image-latest }}

release-python: check test
    #!/usr/bin/env bash
    rm -rf dist/*
    uv build
    export UV_PUBLISH_TOKEN=$(op.exe read op://Secrets/pypi-token/credential)
    uv publish

release-github: check test print-version
    git tag {{ version }}
    git push origin --tags

release-all: release-docker release-python release-github

test:
    pytest

check:
    pre-commit run --all-files --hook-stage manual

update-readme:
    mdsh
