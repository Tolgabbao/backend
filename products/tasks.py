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
    avg_rating = ProductRating.objects.filter(product_id=product_id).aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Update the product with the new average rating
    product.average_rating = avg_rating
    product.save(update_fields=['average_rating'])
    
    return f"Updated average rating for product {product_id} to {avg_rating}"

@shared_task
def notify_low_stock(threshold=5):
    """
    Check for low stock products and notify administrators
    """
    from .models import Product
    
    low_stock_products = Product.objects.filter(stock_quantity__lte=threshold)
    
    if not low_stock_products.exists():
        return "No low stock products found"
    
    product_list = "\n".join([f"- {p.name}: {p.stock_quantity} left" for p in low_stock_products])
    
    send_mail(
        subject='Low Stock Alert',
        message=f"The following products are running low on stock:\n\n{product_list}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.ADMIN_EMAIL],
        fail_silently=False,
    )
    
    return f"Low stock notification sent for {low_stock_products.count()} products"
