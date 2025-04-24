from django.contrib import admin
from django.urls import path, include
from api.views import api_root, status, user_list, item_list, order_list, slow_query, leak_simulation, generate_error

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api_root),
    path("api/status/", status),
    path("api/users/", user_list),
    path("api/items/", item_list),
    path("api/orders/", order_list),
    path("api/slow-query/", slow_query),
    path("api/leak-simulation/", leak_simulation),
    path("api/generate-error/", generate_error),
    path("", include('django_prometheus.urls'))
]
