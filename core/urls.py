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
from products.views import ProductViewSet, CategoryViewSet, get_categories, can_review_product, get_product_comments, get_product_ratings, get_pending_comments, approve_comment
from orders.views import OrderViewSet, CartViewSet, RefundRequestViewSet
from accounts.views import log_in, log_out, get_user, register, address_list, address_detail, set_main_address

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"products", ProductViewSet)
router.register(r"categories", CategoryViewSet)
router.register(r"orders", OrderViewSet, basename="order")
router.register(r"carts", CartViewSet, basename="cart")
router.register(r'refunds', RefundRequestViewSet, basename='refund')

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
    path("api/carts/update/", CartViewSet.update_item, name="update_item"),
    path("api/carts/clear/", CartViewSet.clear_cart, name="clear_cart"),
    path("api/orders/<int:pk>/cancel_order/", OrderViewSet.cancel_order, name="cancel_order"),

    path(
        "api/products/add-product/",
        ProductViewSet.create_product_api,
        name="add_product",
    ),
    path('addresses/', address_list, name='address_list'),
    path('addresses/<int:pk>/', address_detail, name='address_detail'),
    path('addresses/<int:pk>/set-main/', set_main_address, name='set_main_address'),
    path(
        "api/products/<int:product_id>/can-review/",
        can_review_product,
        name="can_review_product",
    ),
    path(
        "api/products/<int:product_id>/comments/",
        get_product_comments,
        name="get_product_comments",
    ),    path(
        "api/products/<int:product_id>/ratings/",
        get_product_ratings,
        name="get_product_ratings",
    ),
    path(
        "api/comments/pending/",
        get_pending_comments,
        name="get_pending_comments",
    ),
    path(
        "api/comments/<int:comment_id>/approve/",
        approve_comment,
        name="approve_comment",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
