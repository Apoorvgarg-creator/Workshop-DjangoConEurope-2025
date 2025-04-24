import time
import random
import logging
import json
import psutil
import os
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.db.backends.signals import connection_created
from django.dispatch import receiver
from django.core.cache import cache
from django.contrib.auth.models import User
from .models import UserProfile, Item, Order, OrderItem
from . import metrics

logger = logging.getLogger(__name__)

@csrf_exempt
def api_root(request):
    """Root API endpoint that lists available endpoints."""
    endpoints = {
        "status": "/api/status/",
        "users": "/api/users/",
        "items": "/api/items/",
        "orders": "/api/orders/",
        "slow_endpoint": "/api/slow-query/",
        "memory_leak": "/api/leak-simulation/",
        "error_generator": "/api/generate-error/"
    }
    return JsonResponse({"available_endpoints": endpoints})

def status(request):
    """Simple status endpoint that returns system metrics."""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    metrics.update_memory_usage(memory_info.rss)
    
    status_data = {
        "status": "operational",
        "memory_usage_mb": memory_info.rss / (1024 * 1024),
        "cpu_percent": process.cpu_percent(interval=0.1),
        "thread_count": process.num_threads(),
        "active_connections": is_connection_active(),
    }
    
    logger.info("Status check performed", extra=status_data)
    return JsonResponse(status_data)

@csrf_exempt
def user_list(request):
    """API endpoint for user management."""
    if request.method == 'GET':
        # Time this database query
        start_time = time.time()
        users = UserProfile.objects.all()
        user_list = [{"id": user.id, "username": user.username, "email": user.email} for user in users]
        duration = time.time() - start_time
        
        # Track the query in our metrics
        metrics.track_db_query('SELECT', 'user_profile', duration)
        
        metrics.active_users_total.set(len(user_list))
        
        return JsonResponse({"users": user_list})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Start timing
            start_time = time.time()
            
            # Create user
            user = UserProfile.objects.create(
                username=data.get('username'),
                email=data.get('email')
            )
            
            duration = time.time() - start_time
            metrics.track_db_query('INSERT', 'user_profile', duration)
            
            logger.info(f"User created: {user.username}", 
                        extra={"user_id": user.id, "email": user.email})
            
            return JsonResponse({"id": user.id, "username": user.username}, status=201)
        
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def item_list(request):
    """API endpoint for item management."""
    if request.method == 'GET':
        # Simulate occasional slow queries
        if random.random() < 0.1:
            time.sleep(0.5)
        
        start_time = time.time()
        items = Item.objects.all()
        item_list = [{"id": item.id, "name": item.name, "price": float(item.price), "stock": item.stock} 
                     for item in items]
        duration = time.time() - start_time
        
        metrics.track_db_query('SELECT', 'item', duration)
        
        return JsonResponse({"items": item_list})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            start_time = time.time()
            item = Item.objects.create(
                name=data.get('name'),
                price=data.get('price'),
                description=data.get('description', ''),
                stock=data.get('stock', 0)
            )
            duration = time.time() - start_time
            
            metrics.track_db_query('INSERT', 'item', duration)
            
            return JsonResponse({
                "id": item.id, 
                "name": item.name,
                "price": float(item.price)
            }, status=201)
            
        except Exception as e:
            logger.error(f"Error creating item: {str(e)}")
            return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def order_list(request):
    """API endpoint for order management."""
    if request.method == 'GET':
        # This query is intentionally inefficient to show N+1 query problems
        start_time = time.time()
        orders = Order.objects.all()
        
        # Detailed information requires fetching related models
        order_list = []
        for order in orders:
            order_items = []
            total_value = 0
            
            # N+1 query problem here (not using select_related/prefetch_related)
            for order_item in OrderItem.objects.filter(order=order):
                item = order_item.item
                item_total = float(item.price) * order_item.quantity
                total_value += item_total
                
                order_items.append({
                    "item_name": item.name,
                    "quantity": order_item.quantity,
                    "unit_price": float(item.price),
                    "total": item_total
                })
            
            order_list.append({
                "id": order.id,
                "user": order.user.username,
                "status": order.status,
                "created_at": order.created_at.isoformat(),
                "items": order_items,
                "total_value": total_value
            })
            
            # Track order value in metrics
            metrics.order_value_total.labels(status=order.status).observe(total_value)
            
        duration = time.time() - start_time
        
        # This query was slow, let's track it
        if duration > 0.1:  # 100ms threshold
            logger.warning(f"Slow order query detected: {duration:.4f}s",
                          extra={"query_time": duration, "order_count": len(orders)})
        
        metrics.track_db_query('SELECT', 'order', duration)
        
        # Calculate cart abandonment rate (simplified example)
        abandoned = Order.objects.filter(status='abandoned').count()
        total = Order.objects.count()
        if total > 0:
            abandonment_rate = abandoned / total
            metrics.cart_abandonment_rate.set(abandonment_rate)
        
        return JsonResponse({"orders": order_list})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Creating an order involves multiple DB operations
            start_time = time.time()
            
            # Get the user
            try:
                user = UserProfile.objects.get(id=data.get('user_id'))
            except UserProfile.DoesNotExist:
                return JsonResponse({"error": "User not found"}, status=404)
            
            # Create the order
            order = Order.objects.create(
                user=user,
                status=data.get('status', 'pending')
            )
            
            # Add items to the order
            total_value = 0
            for item_data in data.get('items', []):
                try:
                    item = Item.objects.get(id=item_data.get('item_id'))
                    quantity = item_data.get('quantity', 1)
                    
                    OrderItem.objects.create(
                        order=order,
                        item=item,
                        quantity=quantity
                    )
                    
                    total_value += float(item.price) * quantity
                    
                except Item.DoesNotExist:
                    logger.warning(f"Item {item_data.get('item_id')} not found for order {order.id}")
            
            duration = time.time() - start_time
            metrics.track_db_query('INSERT', 'order', duration)
            
            # Track order value
            metrics.order_value_total.labels(status=order.status).observe(total_value)
            
            logger.info(f"Order created: {order.id} by user {user.username}",
                       extra={"order_id": order.id, "user_id": user.id, "total_value": total_value})
            
            return JsonResponse({"id": order.id, "status": order.status}, status=201)
            
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            return JsonResponse({"error": str(e)}, status=400)

def slow_query(request):
    """
    Endpoint that intentionally performs a slow database query.
    This demonstrates how to identify problematic queries with monitoring.
    """
    logger.info("Starting slow query execution")
    
    # Simulate a complex, inefficient query
    start_time = time.time()
    
    # Execute a deliberately inefficient query
    with connection.cursor() as cursor:
        # Using raw SQL to demonstrate a poorly optimized query
        cursor.execute("""
            SELECT u.username, COUNT(o.id) as order_count
            FROM api_userprofile u
            LEFT JOIN api_order o ON u.id = o.user_id
            GROUP BY u.username
            ORDER BY order_count DESC
        """)
        results = cursor.fetchall()
    
    # Simulate additional processing time
    time.sleep(random.uniform(0.5, 2.0))
    
    duration = time.time() - start_time
    metrics.track_db_query('COMPLEX_JOIN', 'multiple_tables', duration)
    
    logger.warning(f"Slow query executed in {duration:.4f}s",
                  extra={"query_duration": duration, "query_type": "COMPLEX_JOIN"})
    
    return JsonResponse({
        "message": f"Slow query completed in {duration:.4f} seconds",
        "results_count": len(results)
    })

def leak_simulation(request):
    """
    Endpoint that intentionally creates a memory leak.
    
    This demonstrates how memory leaks can be detected using Prometheus metrics.
    In real applications, memory leaks are often caused by:
    - Long-lived references to objects that should be garbage collected
    - Caches without proper size limits
    - Circular references preventing garbage collection
    """
    logger.info("Memory leak simulation endpoint accessed")
    
    # Get current memory stats before leak
    process = psutil.Process(os.getpid())
    before_mem = process.memory_info().rss / (1024 * 1024)  # MB
    
    # Simulate memory leak
    leak_size = int(request.GET.get('size', '1000'))
    for _ in range(5):  # Create multiple leak objects
        metrics.simulate_memory_leak(request.path, size=leak_size)
    
    # Get memory after leak
    after_mem = process.memory_info().rss / (1024 * 1024)  # MB
    
    logger.warning(f"Memory usage increased from {before_mem:.2f}MB to {after_mem:.2f}MB",
                  extra={
                      "before_memory_mb": before_mem,
                      "after_memory_mb": after_mem,
                      "difference_mb": after_mem - before_mem,
                      "leak_objects": len(metrics.MEMORY_LEAK_CACHE)
                  })
    
    metrics.update_memory_usage(process.memory_info().rss)
    
    return JsonResponse({
        "message": "Memory leak simulated",
        "memory_before_mb": before_mem,
        "memory_after_mb": after_mem,
        "leaked_objects_count": len(metrics.MEMORY_LEAK_CACHE)
    })

def generate_error(request):
    """
    Endpoint that intentionally generates errors for monitoring demonstration.
    
    This shows how errors are captured, logged and alerted on in our monitoring system.
    """
    error_type = request.GET.get('type', 'application')
    
    if error_type == 'application':
        # Log before the error
        logger.info("About to generate an application error")
        # Generate a division by zero error
        result = 1 / 0
        
    elif error_type == 'database':
        # Generate a DB error
        logger.info("About to generate a database error")
        # Try to query a non-existent table
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM nonexistent_table")
            
    elif error_type == 'timeout':
        # Simulate a long-running request that would time out
        logger.info("About to simulate a timeout")
        time.sleep(30)  # Sleep for 30 seconds
        return JsonResponse({"message": "This would normally time out"})
        
    else:
        # Unknown error type
        logger.error(f"Invalid error type requested: {error_type}")
        return JsonResponse({"error": "Invalid error type"}, status=400)
    
    # This code will never be reached due to the errors above
    return JsonResponse({"message": "No error generated"})

def is_connection_active():
    try:
        # Execute a simple test query
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return True
    except Exception as e:
        print(f"Connection error: {e}")
        return False