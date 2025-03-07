"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from products.views import ProductViewSet, CategoryViewSet, get_categories
from orders.views import OrderViewSet, CartViewSet
from accounts.views import log_in, log_out, get_user, register

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"products", ProductViewSet)
router.register(r"categories", CategoryViewSet)
router.register(r"orders", OrderViewSet, basename="order")
router.register(r"carts", CartViewSet, basename="cart")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/auth/", include("rest_framework.urls")),
    path("auth/login/", log_in, name="login"),
    path("auth/logout/", log_out, name="logout"),
    path("auth/user/", get_user, name="get_user"),
    path("auth/register/", register, name="register"),
    path("api/categories/", get_categories, name="get_categories"),
    path("api/carts/add/", CartViewSet.add_item, name="add_item"),
    path("api/carts/remove/", CartViewSet.remove_item, name="remove_item"),
    path("api/carts/items/", CartViewSet.get_items, name="get_items"),
    path(
        "api/products/add-product/",
        ProductViewSet.create_product_api,
        name="add_product",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
