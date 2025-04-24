from django.db import models
from django_prometheus.models import ExportModelOperationsMixin

class UserProfile(ExportModelOperationsMixin('user_profile'), models.Model):
    """
    User profile model with Prometheus metrics integration.
    The ExportModelOperationsMixin adds metrics for create/update/delete operations.
    """
    username = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.username

class Item(ExportModelOperationsMixin('item'), models.Model):
    """
    Item model with Prometheus metrics integration.
    Used for our simulated shopping cart example.
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    stock = models.IntegerField(default=0)
    
    def __str__(self):
        return self.name

class Order(ExportModelOperationsMixin('order'), models.Model):
    """
    Order model with Prometheus metrics integration.
    """
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    items = models.ManyToManyField(Item, through='OrderItem')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pending')
    
    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

class OrderItem(ExportModelOperationsMixin('order_item'), models.Model):
    """
    Order item model with Prometheus metrics integration.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    
    def __str__(self):
        return f"{self.quantity}x {self.item.name} in Order {self.order.id}"