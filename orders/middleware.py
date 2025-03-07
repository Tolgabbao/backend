import uuid
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

class CartSessionMiddleware(MiddlewareMixin):
    """
    Middleware to ensure there's a session ID for anonymous users to associate with their cart.
    """
    
    def process_request(self, request):
        # Only process for anonymous users
        if not request.user.is_authenticated:
            # If no session key exists, create one
            if not request.session.session_key:
                request.session.save()
                
            # Store the session key for later use in views
            request.cart_session_id = request.session.session_key
