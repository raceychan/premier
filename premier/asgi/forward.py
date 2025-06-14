"""
Request forwarding service for ASGI applications.

This module provides the ForwardService class that handles HTTP and WebSocket
request forwarding to backend servers with load balancing support.
"""

import asyncio
from typing import Callable, Dict, List, Optional

from .loadbalancer import ILoadBalancer, RandomLoadBalancer

try:
    import aiohttp
except ImportError:
    raise RuntimeError(
        "aiohttp is required when servers parameter is used. Install with: pip install aiohttp"
    )


class ForwardService:
    """Service for forwarding HTTP and WebSocket requests to backend servers."""

    def __init__(
        self,
        servers: list[str] | None,
        lb_factory: Callable[[List[str]], ILoadBalancer] = RandomLoadBalancer,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """
        Initialize the ForwardService.

        Args:
            load_balancer: Load balancer for selecting backend servers
            session: Optional aiohttp ClientSession (will create one if not provided)
        """
        self.lb = lb_factory(servers or [])
        self._session = session
        self._hop_by_hop_headers = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp ClientSession."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()

    def _build_target_url(self, server_url: str, path: str, query_string: str) -> str:
        """Build the target URL from server URL, path, and query string."""
        target_url = f"{server_url.rstrip('/')}{path}"
        if query_string:
            target_url += f"?{query_string}"
        return target_url

    def _extract_headers(self, scope: dict) -> Dict[str, str]:
        """Extract and clean headers from ASGI scope."""
        headers = {}
        for header_name, header_value in scope.get("headers", []):
            name = header_name.decode("latin1")
            value = header_value.decode("latin1")
            headers[name] = value

        # Remove hop-by-hop headers
        return {
            k: v
            for k, v in headers.items()
            if k.lower() not in self._hop_by_hop_headers
        }

    async def _collect_request_body(self, receive: Callable) -> bytes:
        """Collect the complete request body from ASGI receive callable."""
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break
        return body

    async def _send_response_headers(
        self, send: Callable, response: aiohttp.ClientResponse
    ):
        """Send response headers to ASGI send callable."""
        response_headers = []
        for name, value in response.headers.items():
            # Skip hop-by-hop headers
            if name.lower() not in self._hop_by_hop_headers:
                response_headers.append([name.encode("latin1"), value.encode("latin1")])

        await send(
            {
                "type": "http.response.start",
                "status": response.status,
                "headers": response_headers,
            }
        )

    async def _stream_response_body(
        self, send: Callable, response: aiohttp.ClientResponse
    ):
        """Stream response body from backend to client."""
        async for chunk in response.content.iter_chunked(8192):
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                }
            )

        # Send final empty chunk
        await send(
            {
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            }
        )

    async def _send_error_response(self, send: Callable, error: Exception):
        """Send a 502 error response for proxy errors."""
        error_response = f'{{"error": "Proxy error: {str(error)}"}}'.encode()
        await send(
            {
                "type": "http.response.start",
                "status": 502,
                "headers": [[b"content-type", b"application/json"]],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": error_response,
            }
        )

    async def forward_http_request(
        self, scope: dict, receive: Callable, send: Callable
    ):
        """Forward HTTP request to backend server."""
        server_url = self.lb.choose()

        # Build target URL
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("utf-8")
        target_url = self._build_target_url(server_url, path, query_string)

        # Extract request details
        method = scope.get("method", "GET")
        headers = self._extract_headers(scope)
        body = await self._collect_request_body(receive)

        session = await self._get_session()

        try:
            async with session.request(
                method=method, url=target_url, headers=headers, data=body
            ) as response:
                await self._send_response_headers(send, response)
                await self._stream_response_body(send, response)

        except Exception as e:
            await self._send_error_response(send, e)

    async def forward_websocket_connection(
        self, scope: dict, receive: Callable, send: Callable
    ):
        """Forward WebSocket connection to backend server."""
        server_url = self.lb.choose()

        # Build WebSocket target URL
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("utf-8")
        ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://")
        target_url = self._build_target_url(ws_url, path, query_string)

        # Extract headers
        headers = self._extract_headers(scope)

        session = await self._get_session()

        try:
            async with session.ws_connect(target_url, headers=headers) as ws:
                # Send WebSocket accept
                await send({"type": "websocket.accept"})

                async def forward_from_client():
                    """Forward messages from client to server."""
                    while True:
                        message = await receive()
                        if message["type"] == "websocket.receive":
                            if "bytes" in message:
                                await ws.send_bytes(message["bytes"])
                            elif "text" in message:
                                await ws.send_str(message["text"])
                        elif message["type"] == "websocket.disconnect":
                            await ws.close()
                            break

                async def forward_from_server():
                    """Forward messages from server to client."""
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await send({"type": "websocket.send", "text": msg.data})
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await send({"type": "websocket.send", "bytes": msg.data})
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break

                # Run both forwarding tasks concurrently
                await asyncio.gather(
                    forward_from_client(), forward_from_server(), return_exceptions=True
                )

        except Exception:
            await send(
                {"type": "websocket.close", "code": 1011, "reason": b"Proxy error"}
            )
