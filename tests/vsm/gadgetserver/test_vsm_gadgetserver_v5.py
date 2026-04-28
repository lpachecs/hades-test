import logging

import pytest

from ldf.models.vsm.gadgetserver.vsm_gadgetserver_v5 import (Protocol,
                                                             ResourceType)
from ldf.models.vsm.gadgetserver.vsm_gadgetserver_v5 import \
    VsmGadgetServerV5 as GS

# Test configuration
SERVER_ADDRESS = "10.1.234.224"
SERVER_USERNAME = "vmAdmin"
SERVER_PASSWORD = "vmAdmin"

pytestmark = pytest.mark.dependency


@pytest.fixture(name="gs_server")
def fixture_gs_server() -> GS:
    return GS(address=SERVER_ADDRESS, username=SERVER_USERNAME, password=SERVER_PASSWORD)


class TestVsmGadgetserverV5:

    # ---------------------------------------------------------------------------- #
    #                                 WEB SERVICES                                 #
    # ---------------------------------------------------------------------------- #
    def test_web_connect(self, gs_server: GS):
        response = gs_server._web_connect()
        logging.info("Response: %s", response)
        assert response is not None

    def test_property_url(self, gs_server: GS):
        url = gs_server.url
        logging.info("URL: %s", url)
        assert url is not None

    def test_property_service_hostname(self, gs_server: GS):
        hostname = gs_server.server_hostname
        logging.info("Hostname: %s", hostname)
        assert hostname is not None

    def test_get_service_hostname(self, gs_server: GS):
        hostname = gs_server.get_service_hostname()
        logging.info("Hostname: %s", hostname)
        assert hostname is not None

    def test_get_handles_by_type(self, gs_server: GS):
        handles = gs_server.get_handles_by_type(ResourceType.ALL)
        for handle in handles:
            logging.info("Handle: %s, Type %s", handle[0], handle[1].name)
        assert handles is not None

    def test_get_resources_by_handle(self, gs_server: GS):
        handles = gs_server.get_handles_by_type(ResourceType.ALL)
        for handle in handles[:5]:
            resource = gs_server.get_resource_by_handle(handle[0])
            logging.info("Resource: %s", resource)
            assert resource is not None

    def test_get_resources_by_type(self, gs_server: GS):
        resources = gs_server.get_resources_by_type(ResourceType.PROTOCOL)
        for resource in resources:
            logging.info("Resource: %s", resource)
            assert resource is not None

    def test_get_protocol_factory_by_handle(self, gs_server: GS):
        handles = gs_server.get_handles_by_type(ResourceType.PROTOCOLFACTORY)
        for handle in handles[:1]:
            resource = gs_server.get_protocol_factory_by_handle(handle[0])
            logging.info("Resource: %s", resource.handle)
            assert resource.handle == handle[0]

    def test_get_protocol_by_handle(self, gs_server: GS):
        handles = gs_server.get_handles_by_type(ResourceType.PROTOCOL)
        for handle in handles[:1]:
            resource = gs_server.get_protocol_by_handle(handle[0])
            logging.info("Resource: %s", resource.protocol_handle)
            assert resource.protocol_handle == handle[0]

    def test_get_server_node_by_handle(self, gs_server: GS):
        handles = gs_server.get_handles_by_type(ResourceType.SERVERNODE)
        for handle in handles[:1]:
            resource = gs_server.get_server_node_by_handle(handle[0])
            logging.info("Resource: %s", resource)
            assert resource.handle == handle[0]

    def test_update_resource(self, gs_server: GS):
        handles = gs_server.get_handles_by_type(ResourceType.SERVERNODE)
        for handle in handles[:2]:
            resource = gs_server.get_server_node_by_handle(handle[0])
            if resource.server_node.addresses[0] != gs_server.address:
                continue
            old_comment = resource.server_node.options.comment
            new_comment = "TEST COMMENT"
            resource.server_node.options.comment = new_comment
            updated = gs_server.update_ressource_type(resource)
            logging.info("Resource: %s", updated)
            new_resource = gs_server.get_server_node_by_handle(handle[0])
            assert new_resource.server_node.options.comment == new_comment
            new_resource.server_node.options.comment = old_comment
            gs_server.update_ressource_type(new_resource)

    def test_create_protocol(self, gs_server: GS):
        handles = gs_server.get_handles_by_type(ResourceType.PROTOCOLFACTORY)
        for handle in handles[:1]:
            logging.info("Create new Protocol Handle %s", handle[0])
            new_protocol = Protocol(factory_handle=handle[0])
            new_protocol.settings.display_name = "Test Protocol"
            new_created_protocol = gs_server.create_protocol(new_protocol)
            logging.info("Check if Protocol was created")
            # Get Protocol Handles
            protocol = gs_server.get_protocol_by_handle(new_created_protocol.protocol_handle)
            assert protocol.factory_handle == handle[0]
            if protocol.factory_handle == handle[0]:
                logging.info("Protocol created: %s", protocol.protocol_handle)
                break

    def test_delete_resource(self, gs_server: GS):
        handles = gs_server.get_handles_by_type(ResourceType.PROTOCOLFACTORY)
        for handle in handles[:1]:
            logging.info("Create new Protocol Handle to delete %s", handle[0])
            new_protocol = Protocol(factory_handle=handle[0])
            new_created_protocol = gs_server.create_protocol(new_protocol)
            protocol = gs_server.get_protocol_by_handle(new_created_protocol.protocol_handle)
            assert protocol.factory_handle == handle[0]
            logging.info("Delete Protocol: %s", protocol.protocol_handle)
            assert gs_server.delete_ressource(protocol.protocol_handle)
            # A wrong handle terminates the service...
            with pytest.raises(KeyError):
                gs_server.get_protocol_by_handle(new_created_protocol.protocol_handle)

    def test_get_license(self, gs_server: GS):
        gs_license = gs_server.get_license()
        logging.info("License: %s", gs_license.key)
        assert gs_license.is_licensed is True

    def test_join_server_cluster(self, gs_server: GS):
        pytest.skip("Not implemented yet")

    def test_get_article(self, gs_server: GS):
        handles = gs_server.get_handles_by_type(ResourceType.PROTOCOLFACTORY)
        for handle in handles[:10]:
            article = gs_server.get_article(handle[0])
            logging.info("Article: %s", article)
            assert article is not None

    # ---------------------------------------------------------------------------- #
    #                               WINDOWS SERVICES                               #
    # ---------------------------------------------------------------------------- #

    def test_winrm_connection(self, gs_server: GS):
        assert gs_server.session is not None
        gs_server.session.run_ps("echo 'Hello World'")

    def test_service_status(self, gs_server: GS):
        logging.info("Gadgetserver Service Status: %s", gs_server.status_service)

    def test_service_start(self, gs_server: GS):
        gs_server.start_service()
        logging.info("Gadgetserver Service Status: %s", gs_server.status_service)
        assert gs_server.status_service is True

    def test_service_stop(self, gs_server: GS):
        gs_server.start_service()
        assert gs_server.status_service is True
        gs_server.stop_service()
        logging.info("Gadgetserver Service Status: %s", gs_server.status_service)
        assert gs_server.status_service is False

    def test_service_kill(self, gs_server: GS):
        gs_server.start_service()
        assert gs_server.status_service is True
        gs_server.kill_service()
        logging.info("Gadgetserver Service Status: %s", gs_server.status_service)
        assert gs_server.status_service is False

    def test_service_restart(self, gs_server: GS):
        gs_server.start_service()
        assert gs_server.status_service is True
        gs_server.restart_service()
        logging.info("Gadgetserver Service Status: %s", gs_server.status_service)
        assert gs_server.status_service is True
