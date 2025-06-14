import asyncio
import random
import time
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Create FastAPI app
app = FastAPI(
    title="Example API",
    description="A sample API to demonstrate Premier Gateway features",
    version="1.0.0"
)

# Mock data store
users_db = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "user"},
    3: {"id": 3, "name": "Charlie", "email": "charlie@example.com", "role": "user"},
}

products_db = {
    1: {"id": 1, "name": "Laptop", "price": 999.99, "category": "electronics"},
    2: {"id": 2, "name": "Book", "price": 29.99, "category": "books"},
    3: {"id": 3, "name": "Coffee", "price": 4.99, "category": "beverages"},
}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Quick health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

# User endpoints
@app.get("/api/users")
async def get_users():
    """Get all users - demonstrates caching"""
    # Simulate database delay
    await asyncio.sleep(0.1)
    return {"users": list(users_db.values())}

@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    """Get specific user - demonstrates caching and error handling"""
    # Simulate database delay
    await asyncio.sleep(0.05)
    
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"user": users_db[user_id]}

@app.post("/api/users")
async def create_user(user_data: Dict[str, Any]):
    """Create new user - demonstrates rate limiting"""
    # Simulate processing time
    await asyncio.sleep(0.2)
    
    new_id = max(users_db.keys()) + 1 if users_db else 1
    new_user = {
        "id": new_id,
        "name": user_data.get("name", "Unknown"),
        "email": user_data.get("email", "unknown@example.com"),
        "role": user_data.get("role", "user")
    }
    users_db[new_id] = new_user
    
    return {"message": "User created", "user": new_user}

# Product endpoints
@app.get("/api/products")
async def get_products():
    """Get all products - demonstrates caching with longer TTL"""
    # Simulate slower database query
    await asyncio.sleep(0.3)
    return {"products": list(products_db.values())}

@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    """Get specific product"""
    await asyncio.sleep(0.1)
    
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return {"product": products_db[product_id]}

# Admin endpoints (more restrictive rate limits)
@app.get("/api/admin/stats")
async def get_admin_stats():
    """Admin endpoint with strict rate limiting"""
    await asyncio.sleep(0.5)  # Simulate expensive operation
    
    return {
        "total_users": len(users_db),
        "total_products": len(products_db),
        "system_load": random.uniform(0.1, 0.9),
        "memory_usage": random.uniform(30, 80),
        "timestamp": time.time()
    }

@app.post("/api/admin/cleanup")
async def admin_cleanup():
    """Admin cleanup operation - very restricted"""
    await asyncio.sleep(1.0)  # Simulate long-running operation
    
    return {
        "message": "Cleanup completed",
        "cleaned_items": random.randint(10, 100),
        "timestamp": time.time()
    }

# Slow endpoint to test timeouts
@app.get("/api/slow")
async def slow_endpoint():
    """Intentionally slow endpoint to test timeout features"""
    # This will sometimes timeout with the configured timeout
    delay = random.uniform(3, 8)
    await asyncio.sleep(delay)
    
    return {
        "message": f"Completed after {delay:.2f} seconds",
        "timestamp": time.time()
    }

# Unreliable endpoint to test retry logic
@app.get("/api/unreliable")
async def unreliable_endpoint():
    """Endpoint that randomly fails to test retry logic"""
    if random.random() < 0.6:  # 60% chance of failure
        raise HTTPException(status_code=500, detail="Random server error")
    
    return {
        "message": "Success on retry!",
        "timestamp": time.time()
    }

# Search endpoint with expensive operation
@app.get("/api/search")
async def search(q: str = ""):
    """Search endpoint with expensive operation - good for caching"""
    await asyncio.sleep(0.8)  # Simulate expensive search
    
    # Mock search results
    results = []
    if q:
        for user in users_db.values():
            if q.lower() in user["name"].lower() or q.lower() in user["email"].lower():
                results.append({"type": "user", "data": user})
        
        for product in products_db.values():
            if q.lower() in product["name"].lower() or q.lower() in product["category"].lower():
                results.append({"type": "product", "data": product})
    
    return {
        "query": q,
        "results": results,
        "count": len(results),
        "timestamp": time.time()
    }

# Bulk endpoint for testing rate limiting
@app.post("/api/bulk/process")
async def bulk_process(items: List[Dict[str, Any]]):
    """Bulk processing endpoint - should be rate limited"""
    await asyncio.sleep(0.1 * len(items))  # Processing time based on items
    
    return {
        "message": f"Processed {len(items)} items",
        "processed_count": len(items),
        "timestamp": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)