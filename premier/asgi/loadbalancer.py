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


class RoundRobinLoadBalancer:
    """Round robin load balancer implementation."""
    
    def __init__(self, servers: List[str]):
        """
        Initialize with a list of server URLs.
        
        Args:
            servers: List of server URLs to load balance between
        """
        if not servers:
            raise ValueError("At least one server must be provided")
        self.servers = servers
        self._current_index = 0
    
    def choose(self) -> str:
        """Choose the next server in round robin fashion."""
        server = self.servers[self._current_index]
        self._current_index = (self._current_index + 1) % len(self.servers)
        return server


def create_random_load_balancer(servers: List[str]) -> ILoadBalancer:
    """
    Factory function to create a RandomLoadBalancer.
    
    Args:
        servers: List of server URLs
        
    Returns:
        ILoadBalancer instance
    """
    return RandomLoadBalancer(servers)


def create_round_robin_load_balancer(servers: List[str]) -> ILoadBalancer:
    """
    Factory function to create a RoundRobinLoadBalancer.
    
    Args:
        servers: List of server URLs
        
    Returns:
        ILoadBalancer instance
    """
    return RoundRobinLoadBalancer(servers)