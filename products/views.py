from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse, FileResponse
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.conf import settings
from django.utils.decorators import method_decorator
import logging
from django.db.utils import ProgrammingError

from orders.models import Order
from .models import Product, Category, ProductRating, ProductComment, ProductImage
from .serializers import (
    ProductSerializer,
    CategorySerializer,
    ProductRatingSerializer,
    ProductCommentSerializer,
    ProductImageSerializer,
)
from .tasks import update_product_ratings

logger = logging.getLogger(__name__)

# Cache keys - only keep image-related cache keys
PRODUCT_IMAGE_CACHE_KEY_PREFIX = "product_image_"


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

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        result = super().perform_create(serializer)
        return result

    def perform_update(self, serializer):
        instance = serializer.instance
        result = super().perform_update(serializer)
        return result

    def perform_destroy(self, instance):
        result = super().perform_destroy(instance)
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
        limit = self.request.query_params.get("limit")
        if limit and limit.isdigit():
            queryset = queryset[: int(limit)]

        # Support featured products flag (safely)
        featured = self.request.query_params.get("featured")
        if featured == "true":
            try:
                queryset = queryset.filter(featured=True)
            except (ProgrammingError, Exception) as e:
                logger.warning(f"Featured field error: {str(e)}")

        return queryset

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        result = serializer.save()
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
        return result

    def perform_destroy(self, instance):
        result = super().perform_destroy(instance)
        return result

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Add request to context for building absolute URLs
        context.update({"request": self.request})
        return context

    @action(detail=True, methods=["get"])
    def images(self, request, pk=None):
        """Get all images for a product"""
        product = self.get_object()
        images = ProductImage.objects.filter(product=product)
        serializer = ProductImageSerializer(
            images,
            many=True,
            context={"request": request},  # Pass request in context
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_image(self, request, pk=None):
        """Add a new image to a product"""
        product = self.get_object()

        # Only staff can add images
        if not request.user.is_staff:
            return Response(
                {"error": "Only staff can add images"}, status=status.HTTP_403_FORBIDDEN
            )

        # Handle both multipart form and base64 encoded image
        image_file = request.data.get("image")
        is_primary = request.data.get("is_primary", False)
        alt_text = request.data.get("alt_text", "")

        if not image_file:
            return Response(
                {"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Create ProductImage
        product_image = ProductImage(
            product=product,
            is_primary=is_primary == "true" or is_primary is True,
            alt_text=alt_text,
        )

        # Handle base64 encoded image
        if isinstance(image_file, str) and "base64" in image_file:
            from django.core.files.base import ContentFile
            import base64

            format, imgstr = image_file.split(";base64,")
            ext = format.split("/")[-1]
            file_content = ContentFile(
                base64.b64decode(imgstr),
                name=f"product_{product.id}_{product_image.id}.{ext}",
            )
            product_image.image = file_content
        else:
            # Handle regular file upload
            product_image.image = image_file

        product_image.save()

        return Response(
            ProductImageSerializer(product_image).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["delete"])
    def remove_image(self, request, pk=None):
        """Remove an image from a product"""
        product = self.get_object()

        # Only staff can remove images
        if not request.user.is_staff:
            return Response(
                {"error": "Only staff can remove images"},
                status=status.HTTP_403_FORBIDDEN,
            )

        image_id = request.query_params.get("image_id")
        if not image_id:
            return Response(
                {"error": "No image ID provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            image = ProductImage.objects.get(id=image_id, product=product)
            image.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProductImage.DoesNotExist:
            return Response(
                {"error": "Image not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["post"])
    def set_primary_image(self, request, pk=None):
        """Set an image as primary for a product"""
        product = self.get_object()

        # Only staff can set primary image
        if not request.user.is_staff:
            return Response(
                {"error": "Only staff can set primary image"},
                status=status.HTTP_403_FORBIDDEN,
            )

        image_id = request.data.get("image_id")
        if not image_id:
            return Response(
                {"error": "No image ID provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Set all product images to non-primary first
            ProductImage.objects.filter(product=product).update(is_primary=False)

            # Set the specified image to primary
            image = ProductImage.objects.get(id=image_id, product=product)
            image.is_primary = True
            image.save()

            return Response(ProductImageSerializer(image).data)
        except ProductImage.DoesNotExist:
            return Response(
                {"error": "Image not found"}, status=status.HTTP_404_NOT_FOUND
            )

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
            # Check if user has already rated this product
            existing_rating = ProductRating.objects.filter(user=user, product=product).first()
            if existing_rating:
                # Update existing rating
                existing_rating.rating = serializer.validated_data['rating']
                existing_rating.save()
                message = "Rating updated successfully"
            else:
                # Create new rating
                serializer.save(user=user, product=product)
                message = "Rating submitted successfully"

            # After saving rating, update product's average rating asynchronously
            update_product_ratings.delay(product.id)

            return Response({"message": message, "data": serializer.data})
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
            comment = serializer.save(user=user, product=product)
            
            return Response({
                "message": "Comment submitted successfully and is pending approval", 
                "data": serializer.data
            })
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def approve_comment(self, request, pk=None):
        """Approve a product comment (admin only)"""
        comment_id = request.data.get("comment_id")
        try:
            comment = ProductComment.objects.get(id=comment_id, product__id=pk)
            comment.is_approved = True
            comment.save()
            return Response({"message": "Comment approved successfully"})
        except ProductComment.DoesNotExist:
            return Response({"error": "Comment not found"}, status=404)

    @action(detail=False, methods=["get"])
    def top_rated(self, request):
        """Get top rated products for dashboard"""
        limit = int(request.query_params.get("limit", 6))

        queryset = self.get_queryset()  # This already filters by is_visible

        try:
            products = queryset.order_by("-average_rating")[:limit]
        except Exception as e:
            logger.error(f"Error fetching top rated products: {str(e)}")
            products = queryset[:limit]

        serializer = self.get_serializer(products, many=True)

        # Make sure we return a list, not a dict with 'results' field
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def newest(self, request):
        """Get newest products for dashboard"""
        limit = int(request.query_params.get("limit", 6))

        queryset = self.get_queryset()  # This already filters by is_visible

        try:
            products = queryset.order_by("-created_at")[:limit]
        except Exception as e:
            logger.error(f"Error fetching newest products: {str(e)}")
            products = queryset[:limit]

        serializer = self.get_serializer(products, many=True)

        # Make sure we return a list, not a dict with 'results' field
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def best_selling(self, request):
        """Get best selling products for dashboard"""
        limit = int(request.query_params.get("limit", 6))

        queryset = self.get_queryset()  # This already filters by is_visible

        try:
            products = queryset.order_by("-sales_count")[:limit]
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

        return Response(
            {"id": product.id, "name": product.name, "is_visible": product.is_visible}
        )

    @method_decorator(cache_page(settings.CACHE_TTL))  # Keep caching for images
    @action(detail=True, methods=["get"])
    def image(self, request, pk=None):
        """Endpoint to get the primary/first image for backward compatibility"""
        product = self.get_object()

        # Try to get primary image first
        primary_image = ProductImage.objects.filter(
            product=product, is_primary=True
        ).first()

        # If no primary image, get first image
        if not primary_image:
            primary_image = ProductImage.objects.filter(product=product).first()

        if primary_image and primary_image.image:
            # Generate a cache key for this specific image
            cache_key = f"{PRODUCT_IMAGE_CACHE_KEY_PREFIX}{product.id}"
            
            # Check if image is in cache
            cached_image = cache.get(cache_key)
            if cached_image:
                return FileResponse(cached_image)
                
            # If not in cache, store it
            image_file = primary_image.image.open()
            cache.set(cache_key, image_file, settings.CACHE_TTL)
            return FileResponse(image_file)

        # If no image found, return 404
        return HttpResponse(status=404)


@api_view(["GET"])
def get_product_ratings(request, product_id):
    ratings = ProductRating.objects.filter(product_id=product_id)
    serializer = ProductRatingSerializer(ratings, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def get_product_comments(request, product_id):
    if request.user.is_staff:
        # Admins can see all comments
        comments = ProductComment.objects.filter(product_id=product_id)
    else:
        # Regular users can only see approved comments
        comments = ProductComment.objects.filter(
            product_id=product_id, is_approved=True
        )
    serializer = ProductCommentSerializer(comments, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def get_products_by_category(request, category_id):
    # Only return visible products to regular users
    if request.user.is_staff:
        products = Product.objects.filter(category_id=category_id)
    else:
        products = Product.objects.filter(category_id=category_id, is_visible=True)

    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def get_categories(request):
    categories = Category.objects.all()
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def can_review_product(request, product_id):
    """Check if user can review (rate or comment on) a product"""
    if not request.user.is_authenticated:
        return Response({"can_review": False})
    
    # User can review if they have a delivered order containing this product
    can_review = Order.objects.filter(
        user=request.user, 
        items__product_id=product_id, 
        status="DELIVERED"
    ).exists()
    
    return Response({"can_review": can_review})
