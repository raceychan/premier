import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from .dashboard import DashboardHandler


class DashboardService:
    """
    Dashboard service that handles all dashboard-related HTTP requests.
    
    This service acts as a callable ASGI application for dashboard endpoints,
    encapsulating all dashboard logic in one place.
    """
    
    def __init__(self, config_file_path: Optional[str] = None):
        """
        Initialize the dashboard service.
        
        Args:
            config_file_path: Path to the configuration file for dashboard config operations
        """
        self._handler = DashboardHandler(config_file_path)
    
    def record_request(
        self,
        method: str,
        path: str,
        status: int,
        response_time: float,
        cache_hit: bool = False
    ):
        """Record a request for stats tracking."""
        self._handler.record_request(method, path, status, response_time, cache_hit)
    
    def get_stats_json(self) -> Dict[str, Any]:
        """Get current stats as JSON-serializable dict."""
        return self._handler.get_stats_json()
    
    async def __call__(self, scope: dict, receive: Callable, send: Callable):
        """
        ASGI callable for handling dashboard requests.
        
        Args:
            scope: ASGI scope dict
            receive: ASGI receive callable
            send: ASGI send callable
        """
        path = scope["path"]
        method = scope["method"]

        if path == "/premier/dashboard" and method == "GET":
            await self._handle_dashboard_html(send)
            
        elif path == "/premier/dashboard/api/stats" and method == "GET":
            await self._handle_stats_api(send)
            
        elif path == "/premier/dashboard/api/policies" and method == "GET":
            await self._handle_policies_api(send)
            
        elif path == "/premier/dashboard/api/config" and method == "GET":
            await self._handle_config_get_api(send)
            
        elif path == "/premier/dashboard/api/config" and method == "PUT":
            await self._handle_config_put_api(receive, send)
            
        elif path == "/premier/dashboard/api/config/validate" and method == "POST":
            await self._handle_config_validate_api(receive, send)
            
        else:
            await self._handle_not_found(send)
    
    async def _handle_dashboard_html(self, send: Callable):
        """Handle dashboard HTML page request."""
        html_path = Path(__file__).parent / "dashboard.html"
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/html; charset=utf-8"]],
            })
            await send({
                "type": "http.response.body",
                "body": content.encode("utf-8"),
            })
        except FileNotFoundError:
            await send({
                "type": "http.response.start",
                "status": 404,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"Dashboard not found",
            })
    
    async def _handle_stats_api(self, send: Callable):
        """Handle stats API request."""
        stats_json = json.dumps(self._handler.get_stats_json())
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": stats_json.encode(),
        })
    
    async def _handle_policies_api(self, send: Callable):
        """Handle policies API request."""
        config_dict = None
        if self._handler.config_path:
            config_dict = self._handler.load_config_dict()
        policies_json = json.dumps(self._handler.get_policies_json(config_dict))
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": policies_json.encode(),
        })
    
    async def _handle_config_get_api(self, send: Callable):
        """Handle config GET API request."""
        config_yaml = self._handler.load_config_yaml()
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/plain; charset=utf-8"]],
        })
        await send({
            "type": "http.response.body",
            "body": config_yaml.encode("utf-8"),
        })
    
    async def _handle_config_put_api(self, receive: Callable, send: Callable):
        """Handle config PUT API request."""
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break

        config_yaml = body.decode("utf-8")
        if self._handler.save_config_yaml(config_yaml):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"Configuration saved successfully",
            })
        else:
            await send({
                "type": "http.response.start",
                "status": 400,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"Failed to save configuration",
            })
    
    async def _handle_config_validate_api(self, receive: Callable, send: Callable):
        """Handle config validation API request."""
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break

        config_yaml = body.decode("utf-8")
        result = self._handler.validate_config_yaml(config_yaml)
        result_json = json.dumps(result)
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": result_json.encode(),
        })
    
    async def _handle_not_found(self, send: Callable):
        """Handle 404 for unknown dashboard endpoints."""
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [[b"content-type", b"text/plain"]],
        })
        await send({
            "type": "http.response.body",
            "body": b"Dashboard endpoint not found",
        })