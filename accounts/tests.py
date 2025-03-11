from django.test import TestCase
from django.urls import reverse
from .models import User

class UserAuthenticationTest(TestCase):
    def setUp(self):
        self.login_url = reverse('login') # otomatik olarak login'in URL path'ini döndürüyor
                                          # bizim url path'ımız "/auth/login/", reverse('login') sayesinde
                                          # bunu otomatik olarak kendisi buluyo
        self.register_url = reverse('register')
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpassword'
        }
    def test_login_successful(self):
        """Test login with existent user"""
        #Creating user
        user = User.objects.create_user(username=self.user_data['username'],
                                        email=self.user_data['email'],
                                        password=self.user_data['password'])

        data = {
            "email": "test@example.com",
            "password": "testpassword"
        }

        #response = self.client.post('/auth/login/', data)
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, 200)

        response_data = response.json() # gelen HTTP yanıtının gövdesindeki veriyi
                                        # JSON formatında çözümleyerek Python dictionary
                                        # olarak döndürür
        self.assertEqual(response_data["message"], "User authenticated")
        self.assertEqual(response_data["email"], self.user_data['email'])
        self.assertEqual(response_data["username"], self.user_data['username'])
        self.assertTrue(response.wsgi_request.user.is_authenticated)  # user oturum açmış mı kontrol eder

        #self.assertEqual(response.json().get("message"), "User authenticated")
        #self.assertIn("message", response.data)
        #self.assertEqual(response.json().get("email"), "test@example.com")

    def test_login_nonexistent_user(self):
        """Test login with non-existent user"""
        # wrong email #

        #Creating user
        user = User.objects.create_user(username=self.user_data['username'],
                                        email=self.user_data['email'],
                                        password=self.user_data['password'])

        data = {
            'email': 'nonexistent@example.com',
            'password': 'testpassword'
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, 400)

        response_data = response.json()
        self.assertEqual(response_data['message'], 'Invalid credentials')
        self.assertFalse(response.wsgi_request.user.is_authenticated)  # user oturum açmamış mı kontrol eder

    def test_login_wrong_password(self):
        """Test login with wrong password"""
        #Creating user
        user = User.objects.create_user(username=self.user_data['username'],
                                        email=self.user_data['email'],
                                        password=self.user_data['password'])

        invalid_data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }

        response = self.client.post( self.login_url, invalid_data)
        self.assertEqual(response.status_code, 400)

        response_data = response.json() # gelen HTTP yanıtının gövdesindeki veriyi
                                        # JSON formatında çözümleyerek Python dictionary
                                        # olarak döndürür
        self.assertEqual(response_data['message'], 'Invalid credentials')
        self.assertFalse(response.wsgi_request.user.is_authenticated)  # user oturum açmamış mı kontrol eder

