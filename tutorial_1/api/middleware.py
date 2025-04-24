# api/middleware.py
import logging
import uuid
import random
import time
import traceback
import os
import psutil
from django.conf import settings
from django.http import HttpResponse
from . import metrics

logger = logging.getLogger(__name__)

class RequestContext:
    _request_local = {}
    
    @classmethod
    def get_request_id(cls):
        return cls._request_local.get('request_id', 'no-request-id')
    
    @classmethod
    def set_request_id(cls, request_id):
        cls._request_local['request_id'] = request_id
    
    @classmethod
    def get_user_id(cls):
        return cls._request_local.get('user_id', 'anonymous')
    
    @classmethod
    def set_user_id(cls, user_id):
        cls._request_local['user_id'] = user_id

def request_tracking_middleware(get_response):
    """
    Middleware to track request metrics and add request context.
    
    This middleware:
    1. Generates a unique request ID for tracing
    2. Logs request start/end
    3. Tracks request duration in Prometheus
    4. Captures user information for context
    """
    def middleware(request):
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        RequestContext.set_request_id(request_id)
        request.request_id = request_id
        
        # Set user information
        if request.user.is_authenticated:
            user_id = request.user.id
            RequestContext.set_user_id(user_id)
        else:
            RequestContext.set_user_id('anonymous')
        
        # Start request tracking
        start_time = metrics.track_request_start(request.method, request.path)
        
        # Log request with structured data
        logger.info(f"Request started: {request.method} {request.path}",
                    extra={
                        'request_path': request.path,
                        'request_method': request.method,
                        'request_id': request_id,
                        'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown'),
                        'remote_addr': request.META.get('REMOTE_ADDR', 'unknown'),
                    })
        
        # Update memory usage metrics
        process = psutil.Process(os.getpid())
        metrics.update_memory_usage(process.memory_info().rss)
        
        try:
            # Process the request
            response = get_response(request)
            
            # Track request end
            duration = metrics.track_request_end(
                request.method, request.path, response.status_code, start_time
            )
            
            # Log request completion with structured data
            logger.info(f"Request completed: {request.method} {request.path} - {response.status_code} in {duration:.4f}s",
                        extra={
                            'request_path': request.path,
                            'request_method': request.method,
                            'status_code': response.status_code,
                            'duration': duration,
                            'request_id': request_id,
                        })
            
            return response
            
        except Exception as e:
            # Log exceptions with full context
            logger.error(f"Request failed: {request.method} {request.path} - {str(e)}",
                        extra={
                            'request_path': request.path,
                            'request_method': request.method,
                            'error': str(e),
                            'traceback': traceback.format_exc(),
                            'request_id': request_id,
                        })
            
            # Track the error in metrics
            metrics.track_request_end(request.method, request.path, 500, start_time)
            
            # Re-raise the exception to let Django handle it
            raise
    
    return middleware

def memory_leak_middleware(get_response):
    """
    Middleware to simulate a memory leak for demonstration purposes.
    
    This is an educational example of how memory leaks occur in real-world applications
    and how to detect them with monitoring.
    """
    def middleware(request):
        # Process the request
        response = get_response(request)
        
        # Simulate a memory leak with a certain probability
        leak_probability = getattr(settings, 'MEMORY_LEAK_PROBABILITY', 0.05)
        if random.random() < leak_probability:
            metrics.simulate_memory_leak(request.path)
        
        return response
    
    return middleware

def slow_database_query_middleware(get_response):
    """
    Middleware to simulate slow database queries.
    
    This helps demonstrate how to identify database performance issues.
    """
    def middleware(request):
        # Before request processing
        if 'slow-query' in request.path:
            # Simulate a slow DB query
            time.sleep(random.uniform(0.1, 1.5))  # Simulate random query times
            logger.info("Slow database query detected",
                        extra={'query_time': 1.5, 'table': 'orders'})
            metrics.track_db_query('SELECT', 'orders', 1.5)
        
        # Process the request
        response = get_response(request)
        
        # After request processing
        return response
    
    return middleware
