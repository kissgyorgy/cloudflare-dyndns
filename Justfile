version := "v" + `poetry version -s`
binary-name := "cloudflare-dyndns-linux-x86-" + version
sha256-name := binary-name + ".sha256"
docker-image := "kissgyorgy/cloudflare-dyndns:" + version

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
    podman build -t {{ docker-image }} .

build-all: build-package build-binary build-docker

release-docker:
    podman push kissgyorgy/cloudflare-dyndns:{{ version }}

release-python:
    poetry publish

release-all: release-docker release-python

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
