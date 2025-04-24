from django.contrib import admin
from api.models import UserProfile, Item, OrderItem, Order
# Register your models here.
admin.site.register(UserProfile)
admin.site.register(Item)
admin.site.register(Order)
admin.site.register(OrderItem)
