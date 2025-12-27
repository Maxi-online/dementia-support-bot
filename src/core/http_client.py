import httpx

# Shared async HTTP client instance.
async_client = httpx.AsyncClient(timeout=30.0)
