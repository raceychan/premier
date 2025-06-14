"""
Example application demonstrating Premier API Gateway with dashboard.

Run with:
    uvicorn main:gateway --host 0.0.0.0 --port 8000 --reload

Then visit:
    - http://localhost:8000/premier/dashboard - Premier Dashboard
    - http://localhost:8000/health - Health check
    - http://localhost:8000/api/users - Users API (cached)
    - http://localhost:8000/api/products - Products API (cached)
    - http://localhost:8000/api/admin/stats - Admin endpoint (rate limited)
    - http://localhost:8000/api/search?q=alice - Search API (heavily cached)
"""

from pathlib import Path
from premier.asgi import ASGIGateway, GatewayConfig
from example.fastapi.app import app

# Load configuration
config_path = Path(__file__).parent / "gateway.yaml"
config = GatewayConfig.from_file(config_path)

# Create Premier gateway with the FastAPI app
gateway = ASGIGateway(
    config=config,
    app=app,
    config_file_path=str(config_path.resolve())  # Use absolute path
)

# Export for uvicorn
app = gateway

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Premier API Gateway Example")
    print("📊 Dashboard: http://localhost:8000/premier/dashboard")
    print("🔧 API Docs: http://localhost:8000/docs")
    print("💚 Health: http://localhost:8000/health")
    print()
    
    uvicorn.run(
        "main:gateway",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )