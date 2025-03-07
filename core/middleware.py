from django.http import HttpResponse
import time
import redis
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        try:
            self.redis = redis.Redis.from_url(settings.REDIS_URL)
            self.rate_limit = 2000  # requests per minute
            self.redis_enabled = True
        except redis.exceptions.ConnectionError:
            logger.warning("Redis connection failed - rate limiting disabled")
            self.redis_enabled = False

    def __call__(self, request):
        # Skip rate limiting for admin or if Redis is down
        if request.path.startswith('/admin/') or not self.redis_enabled:
            return self.get_response(request)

        # Get client IP
        ip = self.get_client_ip(request)
        key = f'rate_limit:{ip}'

        try:
            # Check if rate limit exceeded
            current = self.redis.get(key)
            if current and int(current) > self.rate_limit:
                return HttpResponse('Rate limit exceeded. Please try again later.', status=429)

            # Increment request count
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)  # 1 minute expiry
            pipe.execute()
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error in rate limiting: {str(e)}")
            # Continue without rate limiting on Redis errors

        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
