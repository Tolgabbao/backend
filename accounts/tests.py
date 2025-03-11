from django.test import TestCase
from django.urls import reverse
from .models import User

class UserLoginTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpassword")
        self.login_url = reverse('login') # otomatik olarak login'in URL path'ini döndürüyor
                                          # bizim url path'ımız "/auth/login/", reverse('login') sayesinde
                                          # bunu otomatik olarak kendisi buluyo
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpassword'
        }
    def test_login_successful(self):
        """Test login with existent user"""
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
        data = {
            'email': 'nonexistent@example.com',
            'password': 'testpassword'
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, 400)

        response_data = response.json()
        self.assertEqual(response_data['message'], 'Invalid credentials')
        self.assertFalse(response.wsgi_request.user.is_authenticated)  # user oturum açmamış mı kontrol eder

