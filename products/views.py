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
from .models import Product, Category, ProductRating, ProductComment, ProductImage, Wishlist
from .serializers import (
    ProductSerializer,
    CategorySerializer,
    ProductRatingSerializer,
    ProductCommentSerializer,
    ProductImageSerializer,
    WishlistSerializer,
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

    def perform_create(self,serializer):
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionError("User must be authenticated to create categories")

        # Default: allow full save
        if user.user_type == 'PRODUCT_MANAGER':
            # Mark the product as invisible and unapproved until Sales Manager approves
            serializer.save(is_visible=False, price_approved=False)
        else:
            serializer.save()  # Staff/Sales Manager can create normally

        return

    def perform_update(self ,serializer):

        user = self.request.user
        product = serializer.instance

        new_price_raw = serializer.validated_data.get('price')

        try:
            if new_price_raw is not None:
                new_price = float(new_price_raw)

                if new_price != float(product.price):
                    # If a Product Manager is changing the price, revoke approval
                    if user.user_type == 'PRODUCT_MANAGER':
                        serializer.validated_data['price_approved'] = False
                        serializer.validated_data['is_visible'] = False  # optionally hide it until approved

        except (ValueError, TypeError):
            # Handle invalid price input gracefully
            pass
        # Save the updated product now
        return super().perform_update(serializer)

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

    @action(detail=False, methods=["post"], url_path="add-product")
    def create_product_api(self, request):
        """Create a product via API (admin only)"""
        # Check permissions
        if not request.user.is_staff:
            return Response(
                {"error": "Only staff can create products"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        user = self.request.user
        product = serializer.instance

        if user.user_type == 'PRODUCT_MANAGER' and not user.is_staff:
            # Restrict visibility and price approval for Product Manager edits
            serializer.validated_data['is_visible'] = False
            serializer.validated_data['price_approved'] = False

        return super().perform_update(serializer)

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
        return Response(serializer.errors, status=400)    @action(detail=True, methods=["post"])
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

    @action(detail=True, methods=["post"])
    def update_stock(self, request, pk=None):
        """Update product stock quantity (product manager only)"""
        if not (request.user.is_staff or request.user.user_type == 'PRODUCT_MANAGER'):
            return Response(
                {"error": "Only product managers can update stock"},
                status=status.HTTP_403_FORBIDDEN
            )

        product = self.get_object()
        stock_quantity = request.data.get('stock_quantity')

        if stock_quantity is None:
            return Response(
                {"error": "Stock quantity is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            stock_quantity = int(stock_quantity)
            if stock_quantity < 0:
                return Response(
                    {"error": "Stock quantity cannot be negative"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response(
                {"error": "Stock quantity must be a valid number"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if product is going from out of stock to in stock
        current_stock = product.stock_quantity
        is_back_in_stock = current_stock == 0 and stock_quantity > 0

        # Update stock quantity
        product.stock_quantity = stock_quantity
        product.save()

        # If product is back in stock, notify users who have it in their wishlist
        if is_back_in_stock:
            from .tasks import notify_wishlist_back_in_stock
            notify_wishlist_back_in_stock.delay(product.id)

        return Response(self.get_serializer(product).data)
    @action(detail=True, methods=["post"])
    def approve_comment(self, request, pk=None):
        """Approve a product comment (admin or product manager only)"""
        # Check if user is staff or product manager
        if not (request.user.is_staff or request.user.user_type == 'PRODUCT_MANAGER'):
            return Response(
                {"error": "Only staff and product managers can approve comments"},
                status=status.HTTP_403_FORBIDDEN
            )

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

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def add_to_wishlist(self, request, pk=None):
        """Add a product to the user's wishlist"""
        product = self.get_object()
        user = request.user

        # Check if already in wishlist
        wishlist_item, created = Wishlist.objects.get_or_create(user=user, product=product)

        if created:
            return Response({"message": f"{product.name} added to wishlist"}, status=status.HTTP_201_CREATED)
        else:
            return Response({"message": f"{product.name} is already in your wishlist"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], permission_classes=[permissions.IsAuthenticated])
    def remove_from_wishlist(self, request, pk=None):
        """Remove a product from the user's wishlist"""
        product = self.get_object()
        user = request.user

        try:
            wishlist_item = Wishlist.objects.get(user=user, product=product)
            wishlist_item.delete()
            return Response({"message": f"{product.name} removed from wishlist"}, status=status.HTTP_200_OK)
        except Wishlist.DoesNotExist:
            return Response({"error": "Product not in wishlist"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def my_wishlist(self, request):
        """Get the current user's wishlist"""
        wishlist = Wishlist.objects.filter(user=request.user).select_related('product')
        serializer = WishlistSerializer(wishlist, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def set_discount(self, request, pk=None):
        """Set a discount on a product (sales manager only)"""
        if request.user.user_type != 'SALES_MANAGER':
            return Response(
                {"error": "Only sales managers can set discounts"},
                status=status.HTTP_403_FORBIDDEN
            )

        product = self.get_object()
        discount_percent = request.data.get("discount_percent", 0)

        try:
            discount_percent = float(discount_percent)
            if discount_percent < 0 or discount_percent > 100:
                return Response(
                    {"error": "Discount percentage must be between 0 and 100"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # If original price is not set, use current price
            if not product.original_price or product.original_price == 0:
                product.original_price = product.price

            # Update discount and recalculate price
            product.discount_percent = discount_percent
            product.save()  # The save method handles price calculation

            # Notify users who have this product in their wishlist
            if discount_percent > 0:
                from .tasks import notify_wishlist_discount
                notify_wishlist_discount.delay(product.id, discount_percent)

            serializer = self.get_serializer(product)
            return Response(serializer.data)

        except ValueError:
            return Response(
                {"error": "Invalid discount percentage"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def approve_price(self, request, pk=None):
        """Approve a product's price (sales manager only)"""
        if request.user.user_type != 'SALES_MANAGER':
            return Response(
                {"error": "Only sales managers can approve prices"},
                status=status.HTTP_403_FORBIDDEN
            )

        product = self.get_object()

        if product.price <= 0:
            return Response(
                {"error": "Cannot approve a product with price of 0 or less"},
                status=status.HTTP_400_BAD_REQUEST
            )

        product.price_approved = True
        product.is_visible = request.data.get("is_visible", True)  # Optionally make product visible
        product.save()

        serializer = self.get_serializer(product)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def bulk_discount(self, request):
        """Apply discount to multiple products at once (sales manager only)"""
        if request.user.user_type != 'SALES_MANAGER':
            return Response(
                {"error": "Only sales managers can set discounts"},
                status=status.HTTP_403_FORBIDDEN
            )

        product_ids = request.data.get("product_ids", [])
        discount_percent = request.data.get("discount_percent", 0)

        if not product_ids:
            return Response(
                {"error": "No products specified"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            discount_percent = float(discount_percent)
            if discount_percent < 0 or discount_percent > 100:
                return Response(
                    {"error": "Discount percentage must be between 0 and 100"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get products that exist
            products = Product.objects.filter(id__in=product_ids)

            if not products.exists():
                return Response(
                    {"error": "None of the specified products were found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            updated_count = 0
            for product in products:
                # If original price is not set, use current price
                if not product.original_price or product.original_price == 0:
                    product.original_price = product.price

                # Update discount
                product.discount_percent = discount_percent
                product.save()
                updated_count += 1

                # Notify users who have this product in their wishlist
                if discount_percent > 0:
                    from .tasks import notify_wishlist_discount
                    notify_wishlist_discount.delay(product.id, discount_percent)

            return Response({
                "message": f"Discount of {discount_percent}% applied to {updated_count} products",
                "updated_products": updated_count,
                "total_requested": len(product_ids)
            })

        except ValueError:
            return Response(
                {"error": "Invalid discount percentage"},
                status=status.HTTP_400_BAD_REQUEST
            )


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
def get_pending_comments(request):
    """Get pending comments for admin approval"""
    if not request.user.is_staff and request.user.user_type != 'PRODUCT_MANAGER':
        return Response(
            {"error": "Only staff and product managers can view pending comments"},
            status=status.HTTP_403_FORBIDDEN
        )

    # Get all pending comments
    comments = ProductComment.objects.filter(is_approved=False).select_related(
        'product', 'user'
    ).order_by('-created_at')

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


@api_view(["POST"])
def approve_comment(request, comment_id):
    """Approve a specific comment (admin or product manager only)"""
    if not (request.user.is_staff or request.user.user_type == 'PRODUCT_MANAGER'):
        return Response(
            {"error": "Only staff and product managers can approve comments"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        comment = ProductComment.objects.get(id=comment_id)
        comment.is_approved = True
        comment.save()
        return Response({"message": "Comment approved successfully"})
    except ProductComment.DoesNotExist:
        return Response({"error": "Comment not found"}, status=404)
