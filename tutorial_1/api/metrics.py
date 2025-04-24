# api/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Summary
import time
import logging

logger = logging.getLogger(__name__)

# Define custom metrics
http_requests_total = Counter(
    'http_requests_total', 
    'Total HTTP Requests',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
)

http_request_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests in progress',
    ['method', 'endpoint']
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type', 'table']
)

memory_usage_bytes = Gauge(
    'app_memory_usage_bytes',
    'Memory usage in bytes'
)

active_users_total = Gauge(
    'active_users_total',
    'Number of active users'
)

cart_abandonment_rate = Gauge(
    'cart_abandonment_rate',
    'Rate of cart abandonment'
)

order_value_total = Summary(
    'order_value_total',
    'Total value of orders',
    ['status']
)

# Simulated memory leak tracker
memory_leak_objects = Gauge(
    'memory_leak_objects',
    'Number of objects held in memory for the simulated leak'
)

# Global cache for memory leak simulation
MEMORY_LEAK_CACHE = []

def track_request_start(method, endpoint):
    """Track the start of an HTTP request."""
    http_request_in_progress.labels(method=method, endpoint=endpoint).inc()
    return time.time()

def track_request_end(method, endpoint, status_code, start_time):
    """Track the end of an HTTP request with its duration and status code."""
    duration = time.time() - start_time
    http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
    http_request_in_progress.labels(method=method, endpoint=endpoint).dec()
    return duration

def track_db_query(query_type, table, duration):
    """Track database query duration."""
    db_query_duration_seconds.labels(query_type=query_type, table=table).observe(duration)
    logger.debug(f"DB query to {table} ({query_type}) took {duration:.4f}s")

def update_memory_usage(bytes_used):
    """Update the memory usage metric."""
    memory_usage_bytes.set(bytes_used)

def simulate_memory_leak(request_path, size=1000):
    """
    Simulate a memory leak by storing data in a global list.
    
    Args:
        request_path: The path of the request to help identify in metrics
        size: Amount of data to store, representing the leak
    """
    # Only leak on specific endpoints to make it more realistic
    if 'leak' in request_path:
        # Create a large string and store it in our global cache
        large_object = "X" * size * 1000  # Multiply to make it significant
        MEMORY_LEAK_CACHE.append((request_path, large_object))
        memory_leak_objects.set(len(MEMORY_LEAK_CACHE))
        logger.debug(f"Memory leak simulated, objects in cache: {len(MEMORY_LEAK_CACHE)}")
        
        # Add a warning log when the leak gets large enough to cause concern
        if len(MEMORY_LEAK_CACHE) % 10 == 0:
            logger.warning(
                f"Potential memory leak detected! Objects in memory: {len(MEMORY_LEAK_CACHE)}",
                extra={"memory_objects": len(MEMORY_LEAK_CACHE)}
            )