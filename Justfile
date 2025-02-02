version := x"${CURRENT_VERSION}"
binary-name := "cloudflare-dyndns-linux-x86-" + version
sha256-name := binary-name + ".sha256"
docker-image := "kissgyorgy/cloudflare-dyndns"
docker-image-latest := docker-image + ":latest"
docker-image-version := docker-image + ":" + version

help:
    @just --list

clean:
    rm -r build/ dist/ {{ binary-name }} {{ sha256-name }}

build-package:
    uv build

build-docker:
    docker build -t {{ docker-image-version }} .
    docker tag {{ docker-image-version }} {{ docker-image-latest }}

build-all: build-package build-docker

release-docker: build-docker
    docker push {{ docker-image-version }}
    docker push {{ docker-image-latest }}

release-python: build-package
    uv publish

release-github:
    git tag {{ version }}
    git push origin --tags

release-all: release-docker release-python release-github

test:
    pytest

check:
    pre-commit run --all-files --hook-stage manual
