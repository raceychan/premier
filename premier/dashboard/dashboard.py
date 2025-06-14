import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class RequestStats:
    timestamp: float
    method: str
    path: str
    status: int
    response_time: float
    cache_hit: bool = False


@dataclass
class HistoricalSnapshot:
    timestamp: float
    total_requests: int
    cache_hits: int
    cache_misses: int
    rate_limited_requests: int
    total_response_time: float


@dataclass
class GatewayStats:
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limited_requests: int = 0
    total_response_time: float = 0.0
    recent_requests: List[RequestStats] = field(default_factory=list)
    historical_snapshots: List[HistoricalSnapshot] = field(default_factory=list)

    def __post_init__(self):
        if self.recent_requests is None:
            self.recent_requests = []
        if self.historical_snapshots is None:
            self.historical_snapshots = []

    @property
    def cache_hit_rate(self) -> float:
        total_cache_requests = self.cache_hits + self.cache_misses
        if total_cache_requests == 0:
            return 0.0
        return round((self.cache_hits / total_cache_requests) * 100, 1)

    @property
    def avg_response_time(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.total_response_time / self.total_requests, 1)

    def take_snapshot(self):
        """Take a snapshot of current stats for historical tracking"""
        snapshot = HistoricalSnapshot(
            timestamp=time.time(),
            total_requests=self.total_requests,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            rate_limited_requests=self.rate_limited_requests,
            total_response_time=self.total_response_time
        )
        self.historical_snapshots.append(snapshot)
        
        # Keep only last 24 hours of snapshots (assuming 1 snapshot per hour)
        max_snapshots = 24
        if len(self.historical_snapshots) > max_snapshots:
            self.historical_snapshots = self.historical_snapshots[-max_snapshots:]

    def _calculate_change_percentage(self, current: float, previous: float) -> float:
        """Calculate percentage change between current and previous values"""
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return round(((current - previous) / previous) * 100, 1)

    def _get_hourly_change(self, current_value: float, value_getter) -> float:
        """Get the percentage change from one hour ago"""
        one_hour_ago = time.time() - 3600  # 1 hour ago
        
        # Find the closest snapshot to one hour ago
        closest_snapshot = None
        min_time_diff = float('inf')
        
        for snapshot in self.historical_snapshots:
            time_diff = abs(snapshot.timestamp - one_hour_ago)
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                closest_snapshot = snapshot
        
        if not closest_snapshot:
            return 0.0
        
        previous_value = value_getter(closest_snapshot)
        return self._calculate_change_percentage(current_value, previous_value)

    def asdict(self) -> dict[str, str]:
        stats_dict = asdict(self)

        # Add computed properties that aren't included by asdict()
        stats_dict["cache_hit_rate"] = self.cache_hit_rate
        stats_dict["avg_response_time"] = self.avg_response_time

        # Calculate change indicators from historical data
        stats_dict["total_requests_change"] = self._get_hourly_change(
            self.total_requests, lambda s: s.total_requests
        )
        
        # For cache hit rate, we need to calculate the rate from the snapshot
        current_cache_rate = self.cache_hit_rate
        stats_dict["cache_hit_rate_change"] = self._get_hourly_change(
            current_cache_rate, 
            lambda s: round((s.cache_hits / (s.cache_hits + s.cache_misses)) * 100, 1) if (s.cache_hits + s.cache_misses) > 0 else 0.0
        )
        
        stats_dict["rate_limited_change"] = self._get_hourly_change(
            self.rate_limited_requests, lambda s: s.rate_limited_requests
        )
        
        # For avg response time, calculate from snapshot
        current_avg_response = self.avg_response_time
        stats_dict["avg_response_time_change"] = self._get_hourly_change(
            current_avg_response,
            lambda s: round(s.total_response_time / s.total_requests, 1) if s.total_requests > 0 else 0.0
        )

        # Remove historical_snapshots from the dict to avoid sending to frontend
        if "historical_snapshots" in stats_dict:
            del stats_dict["historical_snapshots"]

        # Convert recent requests timestamps to readable format
        for req in stats_dict["recent_requests"]:
            req["timestamp"] = datetime.fromtimestamp(req["timestamp"]).isoformat()

        return stats_dict

    def to_json(self) -> bytes:
        return json.dumps(self.asdict()).encode()


class DashboardHandler:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.stats = GatewayStats()
        self.max_recent_requests = 100
        self.last_snapshot_time = time.time()
        self.snapshot_interval = 3600  # Take snapshot every hour

    def record_request(
        self,
        method: str,
        path: str,
        status: int,
        response_time: float,
        cache_hit: bool = False,
    ):
        """Record a request for stats tracking"""
        # Update overall stats
        self.stats.total_requests += 1
        self.stats.total_response_time += response_time

        if cache_hit:
            self.stats.cache_hits += 1
        else:
            self.stats.cache_misses += 1

        if status == 429:  # Rate limited
            self.stats.rate_limited_requests += 1

        # Add to recent requests
        request_stat = RequestStats(
            timestamp=time.time(),
            method=method,
            path=path,
            status=status,
            response_time=response_time,
            cache_hit=cache_hit,
        )

        self.stats.recent_requests.append(request_stat)

        # Keep only the most recent requests
        if len(self.stats.recent_requests) > self.max_recent_requests:
            self.stats.recent_requests = self.stats.recent_requests[
                -self.max_recent_requests :
            ]
        
        # Take periodic snapshots for historical tracking
        current_time = time.time()
        if current_time - self.last_snapshot_time >= self.snapshot_interval:
            self.stats.take_snapshot()
            self.last_snapshot_time = current_time

    def get_stats_json(self) -> bytes:
        """Get current stats as JSON-serializable dict"""
        return self.stats.to_json()

    def get_policies_json(self, config: Optional[Dict[str, Any]] = None) -> bytes:
        """Extract active policies from config"""
        if not config:
            config = self.load_config_dict()

        policies = []

        if config and "premier" in config and "paths" in config["premier"]:
            for path_config in config["premier"]["paths"]:
                pattern = path_config.get("pattern", "")
                features = list(path_config.get("features", {}).keys())

                policies.append(
                    {
                        "pattern": pattern,
                        "features": features,
                        "request_count": self._get_pattern_request_count(pattern),
                    }
                )

        return json.dumps(policies).encode()

    def _get_pattern_request_count(self, pattern: str) -> int:
        """Get request count for a specific pattern (simplified)"""
        # This is a simplified implementation
        # In a real scenario, you'd want to track this per pattern
        count = 0
        for req in self.stats.recent_requests:
            if self._pattern_matches(pattern, req.path):
                count += 1
        return count

    def _pattern_matches(self, pattern: str, path: str) -> bool:
        """Simple pattern matching (can be enhanced with regex)"""
        if pattern.endswith("*"):
            return path.startswith(pattern[:-1])
        return pattern == path

    def load_config_dict(self) -> Optional[Dict[str, Any]]:
        """Load configuration as dictionary"""
        if not self.config_path:
            return None

        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, "r") as f:
                    return yaml.safe_load(f)
        except Exception:
            pass
        return None

    def load_config_yaml(self) -> str:
        """Load configuration as YAML string"""
        if not self.config_path:
            return "# No configuration file specified"

        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, "r") as f:
                    return f.read()
            else:
                return f"# Configuration file not found: {self.config_path}"
        except Exception as e:
            return f"# Error loading configuration: {str(e)}"

    def save_config_yaml(self, config_yaml: str) -> bool:
        """Save configuration from YAML string"""
        if not self.config_path:
            return False

        try:
            # Validate YAML first
            yaml.safe_load(config_yaml)

            # Save to file
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(config_file, "w") as f:
                f.write(config_yaml)
            return True
        except Exception:
            return False

    def validate_config_yaml(self, config_yaml: str) -> Dict[str, Any]:
        """Validate YAML configuration"""
        try:
            config = yaml.safe_load(config_yaml)

            # Basic validation
            if not isinstance(config, dict):
                return {"valid": False, "error": "Configuration must be a YAML object"}

            if "premier" not in config:
                return {
                    "valid": False,
                    "error": "Configuration must contain 'premier' section",
                }

            # Add more validation as needed
            return {"valid": True}
        except yaml.YAMLError as e:
            return {"valid": False, "error": f"Invalid YAML: {str(e)}"}
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}

    async def handle_dashboard_request(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dashboard HTTP requests"""
        path = scope["path"]
        method = scope["method"]

        if path == "/premier/dashboard" and method == "GET":
            # Return HTML dashboard
            html_path = Path(__file__).parent / "dashboard.html"
            with open(html_path, "r") as f:
                content = f.read()
            return {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/html; charset=utf-8"]],
                "body": content.encode(),
            }

        elif path == "/premier/dashboard/api/stats" and method == "GET":
            # Return JSON stats
            return {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
                "body": self.get_stats_json(),
            }

        elif path == "/premier/dashboard/api/policies" and method == "GET":
            # Return JSON policies
            return {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
                "body": self.get_policies_json(),
            }

        elif path == "/premier/dashboard/api/config" and method == "GET":
            # Return YAML config
            config_yaml = self.load_config_yaml()
            return {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain; charset=utf-8"]],
                "body": config_yaml.encode(),
            }

        elif path == "/premier/dashboard/api/config" and method == "PUT":
            # Save YAML config (body needs to be read from receive callable)
            return {"type": "config_update"}

        elif path == "/premier/dashboard/api/config/validate" and method == "POST":
            # Validate YAML config (body needs to be read from receive callable)
            return {"type": "config_validate"}

        # Return 404 for unknown paths
        return {
            "type": "http.response.start",
            "status": 404,
            "headers": [[b"content-type", b"text/plain"]],
            "body": b"Not Found",
        }
