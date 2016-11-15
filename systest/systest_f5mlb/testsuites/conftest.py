"""Local pytest plugin."""


import functools

import pytest
from pytest import symbols

import systest_common.src as common

from . import utils


DELETE_TIMEOUT = 2 * 60


def pytest_namespace():
    """Configure objects to go in the pytest namespace."""
    bastion = common.ssh.connect(pytest.symbols.bastion)

    def _run(hosts, *args, **kwargs):
        return [str(bastion.run(host, *args, **kwargs)) for host in hosts]

    return {
        'masters_cmd': functools.partial(_run, pytest.symbols.masters),
        'workers_cmd': functools.partial(_run, pytest.symbols.workers)
    }


@pytest.fixture(scope='session', autouse=True)
def orchestration(request):
    """Provide an orchestration connection."""
    return common.orchestration.connect(**vars(symbols))


@pytest.fixture(scope='session', autouse=True)
def ssh(request):
    """Provide an ssh connection - via the bastion host."""
    return common.ssh.connect(gateway=symbols.bastion)


@pytest.fixture(scope='session', autouse=True)
def bigip(request):
    """Provide a bigip connection."""
    return common.bigip.connect(
        symbols.bigip_mgmt_ip,
        utils.DEFAULT_BIGIP_USERNAME,
        utils.DEFAULT_BIGIP_PASSWORD
    )


@pytest.fixture(scope='function', autouse=True)
def default_test_fx(request, orchestration, bigip):
    """Default test fixture.

    Create a test partition on test setup.
    Delete all orchestration apps on test teardown.
    Delete test partition on test teardown.
    """
    def teardown():
        if request.config._meta.vars.get('skip_teardown', None):
            return
        orchestration.namespace = "default"
        orchestration.apps.delete(timeout=DELETE_TIMEOUT)
        orchestration.deployments.delete(timeout=DELETE_TIMEOUT)
        bigip.iapps.delete(partition=partition)
        bigip.virtual_servers.delete(partition=partition)
        bigip.virtual_addresses.delete(partition=partition)
        bigip.pools.delete(partition=partition)
        bigip.nodes.delete(partition=partition)
        bigip.health_monitors.delete(partition=partition)
        bigip.partition.delete(name=partition)

    partition = utils.DEFAULT_F5MLB_PARTITION
    teardown()
    bigip.partition.create(partition, subPath="/")
    # FIXME (kevin): remove these partition hacks when issue #32 is fixed
    p = bigip.partition.get(name=partition)
    p.inheritedTrafficGroup = False
    p.trafficGroup = "/Common/traffic-group-local-only"
    p.update()

    request.addfinalizer(teardown)


@pytest.fixture(scope='function')
def bigip_controller(request, orchestration):
    """Provide a default bigip-controller service."""
    controller = utils.create_bigip_controller(orchestration)

    def teardown():
        if request.config._meta.vars.get('skip_teardown', None):
            return
        orchestration.namespace = "kube-system"
        controller.delete()

    request.addfinalizer(teardown)
    return controller
