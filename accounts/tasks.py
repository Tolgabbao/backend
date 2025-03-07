from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_welcome_email(username, email):
    """
    Send a welcome email to new users after registration
    """
    subject = "Welcome to our E-Commerce Platform!"
    message = f"""
    Hello {username},

    Thank you for registering on our platform. We're excited to have you as a customer!

    Best regards,
    The E-Commerce Team
    """

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,  # Change to True to prevent exceptions
        )
        return f"Welcome email sent to {email}"
    except Exception as e:
        return f"Failed to send email to {email}: {str(e)}"


@shared_task
def send_password_reset_email(user_id, email, reset_token):
    """
    Send a password reset email with token
    """
    subject = "Password Reset Request"
    message = f"""
    You have requested to reset your password.

    Please use the following token to reset your password: {reset_token}

    If you did not request this, please ignore this email.
    """

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )

    return f"Password reset email sent to {email}"
