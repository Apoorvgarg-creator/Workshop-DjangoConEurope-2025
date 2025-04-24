import logging
from .middleware import RequestContext

class RequestIdFilter(logging.Filter):
    """
    This filter adds request_id and user_id to log records.
    
    Having these fields in your logs is crucial for tracing issues
    across multiple services and understanding user context.
    """
    def filter(self, record):
        record.request_id = RequestContext.get_request_id()
        record.user_id = RequestContext.get_user_id()
        return True