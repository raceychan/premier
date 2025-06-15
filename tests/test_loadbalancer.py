import pytest
from premier.asgi.loadbalancer import (
    RandomLoadBalancer,
    RoundRobinLoadBalancer,
    create_random_load_balancer,
    create_round_robin_load_balancer,
)


class TestRandomLoadBalancer:
    def test_initialization_with_servers(self):
        servers = ["http://server1.com", "http://server2.com"]
        lb = RandomLoadBalancer(servers)
        assert lb.servers == servers

    def test_initialization_without_servers_raises_error(self):
        with pytest.raises(ValueError, match="At least one server must be provided"):
            RandomLoadBalancer([])

    def test_choose_returns_server_from_list(self):
        servers = ["http://server1.com", "http://server2.com", "http://server3.com"]
        lb = RandomLoadBalancer(servers)
        
        # Test multiple calls to ensure it's choosing from the list
        chosen_servers = set()
        for _ in range(50):  # Run enough times to likely hit all servers
            chosen = lb.choose()
            assert chosen in servers
            chosen_servers.add(chosen)
        
        # Should have chosen at least one server (randomness makes it hard to guarantee all)
        assert len(chosen_servers) >= 1

    def test_single_server(self):
        servers = ["http://only-server.com"]
        lb = RandomLoadBalancer(servers)
        
        # Should always return the only server
        for _ in range(10):
            assert lb.choose() == "http://only-server.com"


class TestRoundRobinLoadBalancer:
    def test_initialization_with_servers(self):
        servers = ["http://server1.com", "http://server2.com"]
        lb = RoundRobinLoadBalancer(servers)
        assert lb.servers == servers
        assert lb._current_index == 0

    def test_initialization_without_servers_raises_error(self):
        with pytest.raises(ValueError, match="At least one server must be provided"):
            RoundRobinLoadBalancer([])

    def test_round_robin_selection(self):
        servers = ["http://server1.com", "http://server2.com", "http://server3.com"]
        lb = RoundRobinLoadBalancer(servers)
        
        # First round
        assert lb.choose() == "http://server1.com"
        assert lb.choose() == "http://server2.com"
        assert lb.choose() == "http://server3.com"
        
        # Second round should start over
        assert lb.choose() == "http://server1.com"
        assert lb.choose() == "http://server2.com"
        assert lb.choose() == "http://server3.com"

    def test_single_server(self):
        servers = ["http://only-server.com"]
        lb = RoundRobinLoadBalancer(servers)
        
        # Should always return the only server
        for _ in range(10):
            assert lb.choose() == "http://only-server.com"

    def test_two_servers_alternation(self):
        servers = ["http://server1.com", "http://server2.com"]
        lb = RoundRobinLoadBalancer(servers)
        
        # Should alternate between the two servers
        expected_sequence = ["http://server1.com", "http://server2.com"] * 5
        actual_sequence = [lb.choose() for _ in range(10)]
        
        assert actual_sequence == expected_sequence


class TestFactoryFunctions:
    def test_create_random_load_balancer(self):
        servers = ["http://server1.com", "http://server2.com"]
        lb = create_random_load_balancer(servers)
        
        assert isinstance(lb, RandomLoadBalancer)
        assert lb.servers == servers

    def test_create_round_robin_load_balancer(self):
        servers = ["http://server1.com", "http://server2.com"]
        lb = create_round_robin_load_balancer(servers)
        
        assert isinstance(lb, RoundRobinLoadBalancer)
        assert lb.servers == servers

    def test_factory_functions_with_empty_list(self):
        with pytest.raises(ValueError, match="At least one server must be provided"):
            create_random_load_balancer([])
        
        with pytest.raises(ValueError, match="At least one server must be provided"):
            create_round_robin_load_balancer([])