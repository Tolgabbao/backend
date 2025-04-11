from celery import shared_task
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
import time
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle


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

    # Generate PDF with order details
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Add header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, f"Order #{order.id} - Confirmation")
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 70, f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}")
    p.drawString(50, height - 90, f"Customer: {order.user.username}")
    
    # Add shipping address
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, height - 120, "Shipping Address:")
    p.setFont("Helvetica", 12)
    y_position = height - 140
    for line in order.shipping_address.split('\n'):
        p.drawString(50, y_position, line)
        y_position -= 20
    
    # Add order items in a table
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y_position - 20, "Order Items:")
    
    # Create table data
    data = [["Product", "Quantity", "Unit Price", "Subtotal"]]
    for item in order.items.all():
        product_name = item.product.name
        quantity = item.quantity
        price = float(item.price_at_time)
        subtotal = price * quantity
        data.append([product_name, str(quantity), f"${price:.2f}", f"${subtotal:.2f}"])
    
    # Add totals - Fix the format specifier by removing the extra colon
    data.append(["", "", "Total:", f"${float(order.total_amount):.2f}"])
    
    # Create table
    table = Table(data, colWidths=[200, 80, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
    ]))
    
    table.wrapOn(p, width - 100, height)
    table.drawOn(p, 50, y_position - 80 - (len(data) * 20))
    
    # Add footer - use standard Helvetica instead of Helvetica-Italic
    p.setFont("Helvetica", 10)  # Changed from Helvetica-Italic to Helvetica
    p.drawString(50, 50, "Thank you for your order! If you have any questions, please contact our customer service.")
    
    p.showPage()
    p.save()
    
    # Move to the beginning of the buffer
    buffer.seek(0)
    
    # Create email with attachment
    email = EmailMessage(
        subject=f"Order #{order_id} Confirmation",
        body=f"Your order #{order_id} has been received and is being processed. Please find attached the details of your order.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.user.email],
    )
    
    # Attach PDF to email
    email.attach(f'order_{order_id}_confirmation.pdf', buffer.getvalue(), 'application/pdf')
    
    # Send email
    email.send(fail_silently=False)

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
