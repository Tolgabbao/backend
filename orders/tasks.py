from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import time


@shared_task
def process_order(order_id):
    """
    Process order in background, handle inventory updates and payment processing
    """
    # Simulate processing time
    time.sleep(5)

    from .models import Order

    order = Order.objects.get(id=order_id)

    # Update inventory for each product in order
    for item in order.items.all():
        product = item.product
        product.stock_quantity -= item.quantity
        product.save()

    # Update order status
    order.status = "PROCESSING"
    order.save()

    # Send email to customer
    send_mail(
        subject=f"Order #{order_id} Confirmation",
        message=f"Your order #{order_id} has been received and is being processed.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.user.email],
        fail_silently=False,
    )

    return f"Order {order_id} processed successfully"


@shared_task
def send_order_status_update(order_id, new_status):
    """
    Send email notification when order status changes
    """
    from .models import Order

    order = Order.objects.get(id=order_id)

    status_messages = {
        "PROCESSING": "is now being processed",
        "SHIPPED": "has been shipped",
        "DELIVERED": "has been delivered",
        "CANCELLED": "has been cancelled",
    }

    message = f"Your order #{order_id} {status_messages.get(new_status, 'status has been updated')}."

    send_mail(
        subject=f"Order #{order_id} Status Update",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.user.email],
        fail_silently=False,
    )

    return f"Status update email sent for order {order_id}"
