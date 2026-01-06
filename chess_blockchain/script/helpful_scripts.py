"""
Helper functions for deployment scripts
"""

from moccasin.config import get_active_network


def get_contract_address(contract_name: str) -> str:
    """
    Get deployed contract address from deployments.

    Args:
        contract_name: Name of the contract

    Returns:
        Contract address as string
    """
    active_network = get_active_network()
    deployments = active_network.get_deployments()

    if contract_name in deployments:
        return deployments[contract_name]
    else:
        raise ValueError(f"Contract {contract_name} not found in deployments")


def get_network_info():
    """Get information about the active network"""
    active_network = get_active_network()
    return {
        "name": active_network.name,
        "chain_id": active_network.chain_id,
        "is_local": active_network.is_local_or_forked_network(),
    }
