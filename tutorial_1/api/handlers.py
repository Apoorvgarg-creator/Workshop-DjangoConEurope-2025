import logging
import json
import time
import requests
from datetime import datetime

class LokiHandler(logging.Handler):
    """
    Custom log handler to send logs to Loki.
    """ 
    def __init__(self, url='http://localhost:3100/loki/api/v1/push', **kwargs):
        super().__init__()
        self.url = url
        self.batch = []
        self.last_send_time = time.time()
    
    def emit(self, record):
        try:
            # Format the record
            log_entry = self.format(record)
            
            # Extract JSON fields if using JsonFormatter
            try:
                log_data = json.loads(log_entry)
                # Convert to string for Loki
                message = json.dumps(log_data)
            except json.JSONDecodeError:
                # Not JSON, use as is
                message = log_entry
            
            # Create Loki record with labels
            timestamp_ns = int(time.time() * 1_000_000_000)
            
            # Extract attributes for labels
            level = getattr(record, 'levelname', 'INFO').lower()
            request_id = getattr(record, 'request_id', 'no-request-id')
            user_id = getattr(record, 'user_id', 'anonymous')
            module = record.module if hasattr(record, 'module') else 'unknown'
            
            # Create the log entry for Loki
            entry = {
                "stream": {
                    "level": level,
                    "request_id": request_id,
                    "user_id": user_id,
                    "module": module,
                    "app": "django-monitoring-demo"
                },
                "values": [
                    [str(timestamp_ns), message]
                ]
            }
            
            # Add to batch - in production, you'd want to implement proper batching
            self.batch.append(entry)
            
            # Send if batch is full or it's been a while
            if len(self.batch) >= 10 or (time.time() - self.last_send_time) > 5:
                self._send_logs()
                
        except Exception as e:
            # Never let logging break the application
            print(f"Error sending logs to Loki: {e}")
    
    def _send_logs(self):
        """Send the batch of logs to Loki."""
        if not self.batch:
            return
            
        try:
            payload = {
                "streams": self.batch
            }
            
            # In production, add proper error handling, retries, etc.
            response = requests.post(
                self.url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 204:
                print(f"Failed to send logs to Loki: {response.status_code} {response.text}")
                
        except Exception as e:
            print(f"Error sending batch to Loki: {e}")
        finally:
            # Reset batch and update timestamp regardless of success
            self.batch = []
            self.last_send_time = time.time()
            
    def close(self):
        """Send any remaining logs when shutting down."""
        self._send_logs()
        super().close()