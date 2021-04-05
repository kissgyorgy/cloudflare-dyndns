import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--ipv6", action="store_true", default=False, help="Run IPv6 related tests too."
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--ipv6"):
        return
    skip_ipv6 = pytest.mark.skip(reason="need --ipv6 option to run")
    for item in items:
        if "ipv6" in item.keywords:
            item.add_marker(skip_ipv6)
