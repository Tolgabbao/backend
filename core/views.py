from django.http import JsonResponse
from django.middleware.csrf import get_token

"""
def get_csrf_token(request):
    token = get_token(request)
    response = JsonResponse({"csrftoken": token})
    response.set_cookie("csrftoken", token)
    return response
"""