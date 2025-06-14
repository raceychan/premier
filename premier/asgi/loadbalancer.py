import random
from typing import List, Protocol


class ILoadBalancer(Protocol):
    """Protocol for load balancer implementations."""
    
    def choose(self) -> str:
        """Choose a server from the available servers."""
        ...


class RandomLoadBalancer:
    """Random load balancer implementation."""
    
    def __init__(self, servers: List[str]):
        """
        Initialize with a list of server URLs.
        
        Args:
            servers: List of server URLs to load balance between
        """
        if not servers:
            raise ValueError("At least one server must be provided")
        self.servers = servers
    
    def choose(self) -> str:
        """Choose a random server from the available servers."""
        return random.choice(self.servers)


def create_random_load_balancer(servers: List[str]) -> ILoadBalancer:
    """
    Factory function to create a RandomLoadBalancer.
    
    Args:
        servers: List of server URLs
        
    Returns:
        ILoadBalancer instance
    """
    return RandomLoadBalancer(servers)