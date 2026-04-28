import pytest
from datamodel.endpoints import endpoints_pb2

from tests import log

pytestmark = pytest.mark.dependency


@pytest.fixture(params=['Mic/Line', 'MADI', 'AES3', 'IP'])
def source_terminal_type(request):
    return request.param


@pytest.fixture(params=['Line', 'MADI', 'AES3', 'IP'])
def dest_terminal_type(request):
    return request.param


@pytest.fixture
def source_terminal(built_test_device, source_terminal_type):

    for term in built_test_device.terminals(direction='tx'):
        if term.Class == source_terminal_type:
            return term

    pytest.skip(
        f"Failed to find an appropriate {source_terminal_type} source terminal on device {built_test_device.label}"
    )


@pytest.fixture
def dest_terminal(built_test_device, dest_terminal_type):

    for term in built_test_device.terminals(direction='rx'):
        if term.Class == dest_terminal_type:
            return term

    pytest.skip(
        f"Failed to find an appropriate {dest_terminal_type} destination terminal on device {built_test_device.label}"
    )


@pytest.mark.parametrize('dir', ['tx', 'rx'])
@pytest.mark.parametrize('terminal_type', ['IP', 'Mic/Line', 'AES3', 'MADI', 'SDI', 'Line'])
def test_get_internal_terminals(built_test_device, dir, terminal_type):
    """Validate device internal terminal types are expected"""

    matched_terminals = built_test_device.terminals(
        essence=terminal_type, direction=dir
    )
    if len(matched_terminals) == 0:
        pytest.skip(
            f"No matching {terminal_type} terminals found on device. Skipping test."
        )

    for term in matched_terminals:
        log.info(term)
        assert isinstance(term, endpoints_pb2.InternalTerminal)


def test_get_terminal_connections(built_test_device):
    """Validate device internal terminal connections data"""

    for conn in built_test_device.terminals.connections():
        log.info(conn)
        assert isinstance(conn, endpoints_pb2.InternalConnection)


async def test_set_terminal_connections(built_test_device, source_terminal, dest_terminal):
    """Validate various internal terminal types can be routed to destination terminals"""

    log.info("Test internal terminal routing using the following terminals:")
    log.info(f"{source_terminal.ID:<10} -> {dest_terminal.ID}")

    async with built_test_device:
        await built_test_device.terminals.connect(
            [(source_terminal.ID, dest_terminal.ID)]
        )

    for conn in built_test_device.terminals.connections():
        if conn.DstID != dest_terminal.ID:
            continue
        assert conn.SrcID == source_terminal.ID


async def test_disconnect_terminal_connections(built_test_device, source_terminal, dest_terminal):
    """Removes a connection to a given destination terminal"""

    log.info(f"Disconnect source terminal from {dest_terminal.ID}")
    async with built_test_device:
        await built_test_device.terminals.disconnect([dest_terminal.ID])


async def test_disconnect_all_terminal_connections(built_test_device):
    """Removes all connections to all destination terminals"""

    log.info("Disconnect all terminals")
    async with built_test_device:
        await built_test_device.terminals.disconnect_all()

    for conn in built_test_device.terminals.connections():
        assert conn.SrcID == ""
