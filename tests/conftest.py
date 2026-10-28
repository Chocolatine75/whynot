"""`--live` runs tests that call real outside services (free endpoints only); skipped by default."""

import pytest


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", help="run tests that call real APIs (network, FB_TOKEN)")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls real outside services; run with --live")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="needs --live (network)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
