from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.conf import settings
from django.utils.decorators import method_decorator
import logging
from django.db.utils import ProgrammingError

from orders.models import Order
from .models import Product, Category, ProductRating, ProductComment
from .serializers import (
    ProductSerializer,
    CategorySerializer,
    ProductRatingSerializer,
    ProductCommentSerializer,
)
from .tasks import process_product_image, update_product_ratings

logger = logging.getLogger(__name__)

# Cache keys
PRODUCT_LIST_CACHE_KEY = 'product_list'
CATEGORY_LIST_CACHE_KEY = 'category_list'
PRODUCT_DETAIL_CACHE_KEY_PREFIX = 'product_detail_'
CATEGORY_DETAIL_CACHE_KEY_PREFIX = 'category_detail_'

def safe_cache_delete(key):
    """Delete cache key with exception handling"""
    try:
        cache.delete(key)
    except Exception as e:
        logger.error(f"Cache error: {str(e)}")

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @method_decorator(cache_page(settings.CACHE_TTL))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @method_decorator(cache_page(settings.CACHE_TTL))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        result = super().perform_create(serializer)
        safe_cache_delete(CATEGORY_LIST_CACHE_KEY)
        return result
        
    def perform_update(self, serializer):
        instance = serializer.instance
        result = super().perform_update(serializer)
        safe_cache_delete(CATEGORY_LIST_CACHE_KEY)
        safe_cache_delete(f"{CATEGORY_DETAIL_CACHE_KEY_PREFIX}{instance.id}")
        return result
    
    def perform_destroy(self, instance):
        result = super().perform_destroy(instance)
        safe_cache_delete(CATEGORY_LIST_CACHE_KEY)
        safe_cache_delete(f"{CATEGORY_DETAIL_CACHE_KEY_PREFIX}{instance.id}")
        return result

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [
        filters.SearchFilter,
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "description"]
    filterset_fields = ["category"]
    ordering_fields = ["price", "average_rating"]
    
    def get_queryset(self):
        """
        Only return visible products to regular users.
        Staff users can see all products.
        """
        queryset = Product.objects.all()
        
        # If the user is not staff, only show visible products
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_visible=True)
            
        # Handle limit parameter for dashboard widgets
        limit = self.request.query_params.get('limit')
        if limit and limit.isdigit():
            queryset = queryset[:int(limit)]
            
        # Support featured products flag (safely)
        featured = self.request.query_params.get('featured')
        if featured == 'true':
            try:
                queryset = queryset.filter(featured=True)
            except (ProgrammingError, Exception) as e:
                logger.warning(f"Featured field error: {str(e)}")
        
        return queryset

    @method_decorator(cache_page(settings.CACHE_TTL))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @method_decorator(cache_page(settings.CACHE_TTL))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        result = super().perform_create(serializer)
        safe_cache_delete(PRODUCT_LIST_CACHE_KEY)
        # Process image if it exists
        if 'image' in self.request.data:
            process_product_image.delay(serializer.instance.id, serializer.instance.image)
        return result
    
    @action(detail=True, methods=["post"], url_path="add-product")
    def create_product_api(self, request):
        """Create a product via API (admin only)"""
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
            
    def perform_update(self, serializer):
        instance = serializer.instance
        result = super().perform_update(serializer)
        safe_cache_delete(PRODUCT_LIST_CACHE_KEY)
        safe_cache_delete(f"{PRODUCT_DETAIL_CACHE_KEY_PREFIX}{instance.id}")
        return result
    
    def perform_destroy(self, instance):
        result = super().perform_destroy(instance)
        safe_cache_delete(PRODUCT_LIST_CACHE_KEY)
        safe_cache_delete(f"{PRODUCT_DETAIL_CACHE_KEY_PREFIX}{instance.id}")
        return result

    @action(detail=True, methods=["get"])
    def image(self, request, pk=None):
        product = self.get_object()
        if product.image_data:
            return HttpResponse(product.image_data, content_type=product.image_type)
        return HttpResponse(status=404)

    @action(detail=True, methods=["post"])
    def rate_product(self, request, pk=None):
        product = self.get_object()
        user = request.user

        # Check if product is delivered to user
        if not Order.objects.filter(
            user=user, items__product=product, status="DELIVERED"
        ).exists():
            return Response(
                {"error": "You can only rate products you have purchased"}, status=400
            )

        serializer = ProductRatingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user, product=product)
            
            # After saving rating, update product's average rating asynchronously
            update_product_ratings.delay(product.id)
            
            # Clear product cache when rated
            safe_cache_delete(f"{PRODUCT_DETAIL_CACHE_KEY_PREFIX}{pk}")
            
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=["post"])
    def comment_product(self, request, pk=None):
        product = self.get_object()
        user = request.user

        # Similar delivery check as rate_product
        if not Order.objects.filter(
            user=user, items__product=product, status="DELIVERED"
        ).exists():
            return Response(
                {"error": "You can only comment on products you have purchased"},
                status=400,
            )

        serializer = ProductCommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user, product=product)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @action(detail=False, methods=["get"])
    def top_rated(self, request):
        """Get top rated products for dashboard"""
        limit = int(request.query_params.get('limit', 6))
        
        queryset = self.get_queryset()  # This already filters by is_visible
        
        try:
            products = queryset.order_by('-average_rating')[:limit]
        except Exception as e:
            logger.error(f"Error fetching top rated products: {str(e)}")
            products = queryset[:limit]
            
        serializer = self.get_serializer(products, many=True)
        
        # Make sure we return a list, not a dict with 'results' field
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def newest(self, request):
        """Get newest products for dashboard"""
        limit = int(request.query_params.get('limit', 6))
        
        queryset = self.get_queryset()  # This already filters by is_visible
        
        try:
            products = queryset.order_by('-created_at')[:limit]
        except Exception as e:
            logger.error(f"Error fetching newest products: {str(e)}")
            products = queryset[:limit]
            
        serializer = self.get_serializer(products, many=True)
        
        # Make sure we return a list, not a dict with 'results' field
        return Response(serializer.data)
    
    @action(detail=False, methods=["get"])
    def best_selling(self, request):
        """Get best selling products for dashboard"""
        limit = int(request.query_params.get('limit', 6))
        
        queryset = self.get_queryset()  # This already filters by is_visible
        
        try:
            products = queryset.order_by('-sales_count')[:limit]
        except (ProgrammingError, Exception) as e:
            logger.error(f"Error fetching best-selling products: {str(e)}")
            products = queryset[:limit]
            
        serializer = self.get_serializer(products, many=True)
        
        # Make sure we return a list, not a dict with 'results' field
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def toggle_visibility(self, request, pk=None):
        """Toggle product visibility (admin only)"""
        product = self.get_object()
        product.is_visible = not product.is_visible
        product.save()
        
        # Clear cache
        safe_cache_delete(f"{PRODUCT_DETAIL_CACHE_KEY_PREFIX}{product.id}")
        safe_cache_delete(PRODUCT_LIST_CACHE_KEY)
        
        return Response({
            "id": product.id,
            "name": product.name,
            "is_visible": product.is_visible
        })

@cache_page(settings.CACHE_TTL)
@api_view(["GET"])
def get_product_ratings(request, product_id):
    ratings = ProductRating.objects.filter(product_id=product_id)
    serializer = ProductRatingSerializer(ratings, many=True)
    return Response(serializer.data)


@cache_page(settings.CACHE_TTL)
@api_view(["GET"])
def get_product_comments(request, product_id):
    comments = ProductComment.objects.filter(product_id=product_id)
    serializer = ProductCommentSerializer(comments, many=True)
    return Response(serializer.data)


@cache_page(settings.CACHE_TTL)
@api_view(["GET"])
def get_products_by_category(request, category_id):
    # Only return visible products to regular users
    if request.user.is_staff:
        products = Product.objects.filter(category_id=category_id)
    else:
        products = Product.objects.filter(category_id=category_id, is_visible=True)
        
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)


@cache_page(settings.CACHE_TTL)
@api_view(["GET"])
def get_categories(request):
    categories = Category.objects.all()
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)
