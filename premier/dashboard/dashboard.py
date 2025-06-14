import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

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
class GatewayStats:
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limited_requests: int = 0
    total_response_time: float = 0.0
    recent_requests: List[RequestStats] = None
    
    def __post_init__(self):
        if self.recent_requests is None:
            self.recent_requests = []
    
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


class DashboardHandler:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.stats = GatewayStats()
        self.max_recent_requests = 100
        
    def record_request(
        self,
        method: str,
        path: str,
        status: int,
        response_time: float,
        cache_hit: bool = False
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
            cache_hit=cache_hit
        )
        
        self.stats.recent_requests.append(request_stat)
        
        # Keep only the most recent requests
        if len(self.stats.recent_requests) > self.max_recent_requests:
            self.stats.recent_requests = self.stats.recent_requests[-self.max_recent_requests:]
    
    def get_stats_json(self) -> Dict[str, Any]:
        """Get current stats as JSON-serializable dict"""
        stats_dict = asdict(self.stats)
        
        # Convert recent requests timestamps to readable format
        for req in stats_dict['recent_requests']:
            req['timestamp'] = datetime.fromtimestamp(req['timestamp']).isoformat()
        
        return stats_dict
    
    def get_policies_json(self, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract active policies from config"""
        if not config:
            config = self.load_config_dict()
            
        policies = []
        
        if config and 'premier' in config and 'paths' in config['premier']:
            for path_config in config['premier']['paths']:
                pattern = path_config.get('pattern', '')
                features = list(path_config.get('features', {}).keys())
                
                policies.append({
                    'pattern': pattern,
                    'features': features,
                    'request_count': self._get_pattern_request_count(pattern)
                })
        
        return policies
    
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
        if pattern.endswith('*'):
            return path.startswith(pattern[:-1])
        return pattern == path
    
    def load_config_dict(self) -> Optional[Dict[str, Any]]:
        """Load configuration as dictionary"""
        if not self.config_path:
            return None
            
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
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
                with open(config_file, 'r') as f:
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
            
            with open(config_file, 'w') as f:
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
            
            if 'premier' not in config:
                return {"valid": False, "error": "Configuration must contain 'premier' section"}
            
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
            with open(html_path, 'r') as f:
                content = f.read()
            return {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/html; charset=utf-8"]],
                "body": content.encode()
            }
        
        elif path == "/premier/dashboard/api/stats" and method == "GET":
            # Return JSON stats
            stats_json = json.dumps(self.get_stats_json())
            return {
                "type": "http.response.start", 
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
                "body": stats_json.encode()
            }
        
        elif path == "/premier/dashboard/api/policies" and method == "GET":
            # Return JSON policies
            policies_json = json.dumps(self.get_policies_json())
            return {
                "type": "http.response.start",
                "status": 200, 
                "headers": [[b"content-type", b"application/json"]],
                "body": policies_json.encode()
            }
        
        elif path == "/premier/dashboard/api/config" and method == "GET":
            # Return YAML config
            config_yaml = self.load_config_yaml()
            return {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain; charset=utf-8"]],
                "body": config_yaml.encode()
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
            "body": b"Not Found"
        }