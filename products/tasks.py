from celery import shared_task
import time
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def process_product_image(product_id, image_path):
    """
    Process uploaded product images (resize, optimize, create thumbnails)
    """
    # Simulate image processing
    time.sleep(3)

    from .models import Product

    product = Product.objects.get(id=product_id)

    # Implement actual image processing here
    # For example: resize, create thumbnails, optimize

    return f"Image for product {product_id} processed successfully"


@shared_task
def update_product_ratings(product_id):
    """
    Recalculate average rating for a product
    """
    from .models import Product, ProductRating
    from django.db.models import Avg

    product = Product.objects.get(id=product_id)
    avg_rating = (
        ProductRating.objects.filter(product_id=product_id).aggregate(Avg("rating"))[
            "rating__avg"
        ]
        or 0
    )

    # Update the product with the new average rating
    product.average_rating = avg_rating
    product.save(update_fields=["average_rating"])

    return f"Updated average rating for product {product_id} to {avg_rating}"


@shared_task
def notify_wishlist_discount(product_id, discount_percent):
    """
    Notify users when a product in their wishlist has a discount applied
    """
    from .models import Product, Wishlist
    
    try:
        product = Product.objects.get(id=product_id)
        
        # Get all users who have this product in their wishlist
        wishlist_users = Wishlist.objects.filter(product=product).select_related('user')
        
        if not wishlist_users.exists():
            return f"No users have product {product_id} in their wishlist"
        
        # Send email to each user
        for wishlist in wishlist_users:
            user = wishlist.user
            subject = f"Discount Alert: {product.name} is now on sale!"
            message = f"""
            Hello {user.username},
            
            Good news! A product in your wishlist is now on discount:
            
            {product.name} - {discount_percent}% OFF
            
            Original price: ${product.original_price}
            Discounted price: ${product.price}
            
            Don't miss this opportunity!
            
            Best regards,
            The E-Commerce Team
            """
            
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Failed to send discount notification to {user.email}: {str(e)}")
        
        return f"Discount notifications sent to {wishlist_users.count()} users for product {product_id}"
    except Product.DoesNotExist:
        return f"Product with ID {product_id} not found"
    except Exception as e:
        return f"Error sending discount notifications: {str(e)}"


@shared_task
def notify_low_stock(threshold=5):
    """
    Check for low stock products and notify administrators
    """
    from .models import Product

    low_stock_products = Product.objects.filter(stock_quantity__lte=threshold)

    if not low_stock_products.exists():
        return "No low stock products found"

    product_list = "\n".join(
        [f"- {p.name}: {p.stock_quantity} left" for p in low_stock_products]
    )

    send_mail(
        subject="Low Stock Alert",
        message=f"The following products are running low on stock:\n\n{product_list}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.ADMIN_EMAIL],
        fail_silently=False,
    )

    return f"Low stock notification sent for {low_stock_products.count()} products"
