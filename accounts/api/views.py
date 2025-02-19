from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt

"""
export const authApi = {
  login: async (email: string, password: string) => {
    const response = await fetch(`${BASE_URL}/api/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      credentials: 'include',
    });

    if (!response.ok) throw new Error('Login failed');
    return response.json();
  },

  checkAuthStatus: async () => {
    const response = await fetch(`${BASE_URL}/api/auth/status/`, {
      credentials: 'include'
    });
    return response.ok;
  }
};
"""

@api_view(['POST'])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response({'error': 'Please provide both email and password'}, status=400)

    user = authenticate(username=email, password=password)  # Django uses username field for authentication

    if user is not None:
        login(request, user)
        return Response({
            'message': 'Login successful',
            'user': {
                'email': user.email,
                'id': user.id
            }
        })
    return Response({'error': 'Invalid credentials'}, status=401)

@api_view(['GET'])
def status(request):
    if request.user.is_authenticated:
        return Response({'isAuthenticated': True})
    return Response({'isAuthenticated': False})

@api_view(['POST'])
def logout(request):
    logout(request)
    return Response({'message': 'Logout successful'})

@api_view(['POST'])
def register(request):
    email = request.data.get('email')
    password = request.data.get('password')
    user = User.objects.create_user(email=email, password=password)
    return Response({'message': 'User created successfully'})

@api_view(['POST'])
def change_password(request):
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    if not user.check_password(old_password):
        return Response({'error': 'Invalid password'}, status=400)
    user.set_password(new_password)
    user.save()
    return Response({'message': 'Password changed successfully'})

@api_view(['POST'])
def reset_password(request):
    email = request.data.get('email')
    user = User.objects.get(email=email)
    new_password = User.objects.make_random_password()
    user.set_password(new_password)
    user.save()
    return Response({'message': 'Password reset successfully'})

@api_view(['POST'])
def change_email(request):
    user = request.user
    new_email = request.data.get('new_email')
    user.email = new_email
    user.save()
    return Response({'message': 'Email changed successfully'})
