"""
Example usage of VsmGadgetServerV6 to create a protocol.

This example shows how to create a protocol using the factoryHandle a5c0289d-fd4b-4916-876d-0f3c826f0eaa
"""

from ldf.models.vsm.gadgetserver.vsm_gadgetserver_v6 import VsmGadgetServerV6
from ldf.models.vsm.gadgetserver.vsm_gadgetserver_v6_resources import (
    ProtocolContract, ProtocolSettings)


def create_protocol_example():
    # Initialize the API client
    api = VsmGadgetServerV6(
        address="wib-rd-atest-1a",
        username="your_username",
        password="your_password"
    )

    # Method 1: Create protocol using ProtocolContract (recommended)
    # NOTE: POST method only allows displayName and addressCollection to be set
    # Other settings must be updated after creation using PUT

    # Create protocol settings with only allowed fields for creation
    settings = ProtocolSettings(
        display_name="My Test Protocol",
        address_collection=["9000"]  # Only displayName and addressCollection allowed in POST
    )

    # Create the protocol contract
    protocol = ProtocolContract(
        factory_id="a5c0289d-fd4b-4916-876d-0f3c826f0eaa",
        settings=settings
    )

    try:
        # Create the protocol
        response = api.create_protocol(protocol)
        print(f"Protocol created successfully: {response}")

        # Extract the created protocol ID for future operations
        if response and len(response) > 0:
            created_protocol_id = response[0].get("id")
            print(f"Created protocol ID: {created_protocol_id}")

            # Now update the protocol with additional settings
            if created_protocol_id:
                edit_protocol_example(api, created_protocol_id)

    except Exception as e:
        print(f"Error creating protocol: {e}")

    # Method 2: Create protocol using raw dictionary
    # NOTE: Only displayName and addressCollection are allowed during creation

    protocol_dict = {
        "factoryId": "a5c0289d-fd4b-4916-876d-0f3c826f0eaa",
        "settings": {
            "displayName": "My Test Protocol (Raw)",
            "addressCollection": ["9000"]
            # Other settings will be added after creation via PUT
        }
    }

    try:
        response = api.create_protocol(protocol_dict)
        print(f"Protocol created from dict: {response}")

        # Update with additional settings after creation
        if response and len(response) > 0:
            created_protocol_id = response[0].get("id")
            if created_protocol_id:
                edit_protocol_example(api, created_protocol_id)

    except Exception as e:
        print(f"Error creating protocol from dict: {e}")


def edit_protocol_example(api: VsmGadgetServerV6, protocol_id: str):
    """Example of how to edit/update a protocol after creation.

    Args:
        api: VsmGadgetServerV6 instance
        protocol_id: ID of the protocol to update
    """
    try:
        # First, get the current protocol configuration
        current_protocol = api.get_protocol(protocol_id)
        print(f"Current protocol configuration: {current_protocol}")

        # Create a ProtocolContract from the current state
        protocol_contract = ProtocolContract(dictionary=current_protocol)

        # Now update the settings that couldn't be set during creation
        protocol_contract.settings.is_enabled = True
        protocol_contract.settings.binding_interface = "any"
        protocol_contract.settings.stream_type = 1

        # Add protocol-specific options
        protocol_contract.settings.add_single_option("Logging", "False")
        protocol_contract.settings.add_single_option("AutoConnect", "True")
        protocol_contract.settings.add_single_option("RetryCount", "3")

        # Add multi-value options if needed
        protocol_contract.settings.add_multi_option("SupportedFormats", ["PCM", "DSD"])

        # Update the protocol using PUT
        response = api.update_protocol(protocol_id, protocol_contract.to_dict())
        print(f"Protocol updated successfully: {response}")

        # Verify the update by getting the protocol again
        updated_protocol = api.get_protocol(protocol_id)
        print(f"Updated protocol configuration: {updated_protocol}")

    except Exception as e:
        print(f"Error updating protocol: {e}")


def update_specific_protocol_setting(protocol_id: str, setting_name: str, setting_value: str):
    """Example of updating a specific protocol setting.

    Args:
        protocol_id: ID of the protocol to update
        setting_name: Name of the setting to update
        setting_value: New value for the setting
    """
    api = VsmGadgetServerV6(
        address="wib-rd-atest-1a",
        username="your_username",
        password="your_password"
    )

    try:
        # Get current protocol
        current_protocol = api.get_protocol(protocol_id)
        protocol_contract = ProtocolContract(dictionary=current_protocol)

        # Find and update the specific setting
        setting_found = False
        for option in protocol_contract.settings.single_value_options:
            if option.name == setting_name:
                option.value_as_string = setting_value
                setting_found = True
                break

        # If setting doesn't exist, add it
        if not setting_found:
            protocol_contract.settings.add_single_option(setting_name, setting_value)

        # Update the protocol
        response = api.update_protocol(protocol_id, protocol_contract.to_dict())
        print(f"Setting '{setting_name}' updated to '{setting_value}': {response}")

    except Exception as e:
        print(f"Error updating protocol setting: {e}")


def list_available_factories():
    """Helper function to list available protocol factories"""
    api = VsmGadgetServerV6(
        address="wib-rd-atest-1a",
        username="your_username",
        password="your_password"
    )

    try:
        factories = api.get_protocol_factories()
        print("Available Protocol Factories:")
        for factory in factories:
            print(f"  - ID: {factory.get('id', 'N/A')}")
            print(f"    Name: {factory.get('name', 'N/A')}")
            print(f"    Description: {factory.get('description', 'N/A')}")
            print()
    except Exception as e:
        print(f"Error getting protocol factories: {e}")


def list_existing_protocols():
    """Helper function to list existing protocols"""
    api = VsmGadgetServerV6(
        address="wib-rd-atest-1a",
        username="your_username",
        password="your_password"
    )

    try:
        protocols = api.get_protocols()
        print("Existing Protocols:")
        for protocol in protocols:
            print(f"  - ID: {protocol.get('id', 'N/A')}")
            print(f"    Factory ID: {protocol.get('factoryId', 'N/A')}")
            print(f"    Display Name: {protocol.get('settings', {}).get('displayName', 'N/A')}")
            print(f"    Enabled: {protocol.get('settings', {}).get('isEnabled', 'N/A')}")
            print()
    except Exception as e:
        print(f"Error getting protocols: {e}")


if __name__ == "__main__":
    # Uncomment the functions you want to run:

    # List available factories first to see what's available
    # list_available_factories()

    # List existing protocols
    # list_existing_protocols()

    # Create a new protocol (includes automatic editing after creation)
    # create_protocol_example()

    # Update a specific setting on an existing protocol
    # update_specific_protocol_setting("your-protocol-id", "Logging", "True")

    print("Example script completed. Uncomment the functions above to run them.")
    print("\nNOTE: The REST API only allows displayName and addressCollection to be set during creation.")
    print("All other settings must be updated after creation using the update_protocol method.")
