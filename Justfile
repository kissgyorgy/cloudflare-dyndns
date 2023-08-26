version := "v" + `poetry version -s`
binary-name := "cloudflare-dyndns-linux-x86-" + version
sha256-name := binary-name + ".sha256"
docker-image := "kissgyorgy/cloudflare-dyndns"
docker-image-latest := docker-image + ":latest"
docker-image-version := docker-image + ":" + version

install:
    poetry install

clean:
    rm -r build/ dist/ {{ binary-name }} {{ sha256-name }}

build-package:
    poetry build

build-binary: requirements-txt
    pyoxidizer build
    mv ./build/x86_64-unknown-linux-gnu/debug/install/cloudflare-dyndns {{ binary-name }}
    sha256sum {{ binary-name }} > {{ sha256-name }}

build-docker:
    podman build -t docker.io/{{ docker-image-version }} .
    podman tag docker.io/{{ docker-image-version }} docker.io/{{ docker-image-latest }}

build-all: build-package build-binary build-docker

release-docker: build-docker
    podman push docker.io/{{ docker-image-version }}
    podman push docker.io/{{ docker-image-latest }}

release-python: build-package
    poetry publish

github:
    git tag {{ version }}
    git push origin --tags

release-all: release-docker release-python github

requirements-txt:
    poetry export -o requirements.txt
    just _modify-requirements-txt > requirements.new
    mv requirements.new requirements.txt

_modify-requirements-txt:
    #!/usr/bin/env python3
    from pathlib import Path
    import re

    requirements_txt = Path("requirements.txt").read_text()

    # Remove pyyaml dependency completely
    new_requirements = re.sub(
        r"pyyaml(.*\\\n)*.*[^\\]\n",
        "",
        requirements_txt,
        flags=re.MULTILINE
    )

    # Add --no-binary pydantic option to the next line of pydantic
    new_requirements = re.sub(
        r"(pydantic.*\\)\n",
        r"\1\n    --no-binary pydantic \\\n",
        new_requirements,
        flags=re.MULTILINE
    )

    print(new_requirements, end="")
