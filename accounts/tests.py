from django.test import TestCase, Client
from django.urls import reverse
from .models import User
from .models import Address

class UserAuthenticationTest(TestCase):
    def setUp(self):
        self.login_url = reverse('login') # otomatik olarak login'in URL path'ini döndürüyor
                                          # bizim url path'ımız "/auth/login/", reverse('login') sayesinde
                                          # bunu otomatik olarak kendisi buluyo
        self.register_url = reverse('register')
        self.logout_url = reverse('logout')
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpassword'
        }

    """Test login with existent user"""
    def test_login_successful(self):

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


    """Test login with non-existent user"""
    def test_login_nonexistent_user(self):
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

    """Test login with wrong password"""
    def test_login_wrong_password(self):
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

    """Test login with missing password"""
    def test_login_missing_password(self):
        #Creating user
        user = User.objects.create_user(username=self.user_data['username'],
                                        email=self.user_data['email'],
                                        password=self.user_data['password'])

        missing_data = {
            'email': 'test@example.com',
            #missing password
        }

        response = self.client.post( self.login_url, missing_data)
        self.assertEqual(response.status_code, 400)

        response_data = response.json() # gelen HTTP yanıtının gövdesindeki veriyi
                                        # JSON formatında çözümleyerek Python dictionary
                                        # olarak döndürür

        self.assertEqual(response_data['message'], 'Invalid credentials')
        self.assertFalse(response.wsgi_request.user.is_authenticated)  # user oturum açmamış mı kontrol eder

    """Test login with missing email"""
    def test_login_missing_email(self):
        #Creating user
        user = User.objects.create_user(username=self.user_data['username'],
                                        email=self.user_data['email'],
                                        password=self.user_data['password'])

        missing_data = {
            #missing email
            'password': "testpassword"
        }

        response = self.client.post( self.login_url, missing_data)
        self.assertEqual(response.status_code, 400)

        response_data = response.json() # gelen HTTP yanıtının gövdesindeki veriyi
                                        # JSON formatında çözümleyerek Python dictionary
                                        # olarak döndürür

        self.assertEqual(response_data['message'], 'Invalid credentials')
        self.assertFalse(response.wsgi_request.user.is_authenticated)  # user oturum açmamış mı kontrol eder

    """Test successful user registration"""
    def test_register_success(self):


        response = self.client.post(self.register_url, self.user_data) # mock kullanıcı oluşturur, test bitince silinir
        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        self.assertEqual(response_data['message'], 'User created')

        # Verify user was created in the database
        self.assertTrue(User.objects.filter(email=self.user_data['email']).exists())

        # Verify user has correct attributes
        user = User.objects.get(email=self.user_data['email'])
        self.assertEqual(user.username, self.user_data['username'])

    """Test registration with duplicate email"""
    def test_register_duplicate_email(self):
        # Create a user
        user = User.objects.create_user(username=self.user_data['username'],
                                        email=self.user_data['email'],
                                        password=self.user_data['password'])

        # Try to register another user with the same email
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, 400)

        response_data = response.json()
        self.assertIn('User already exists', response_data['message']) # response'nin içinde
                                                                               # 'user already exists'
                                                                               # var mı diye kontrol eder

    """Test logout for an authenticated user"""
    def test_logout_authenticated_user(self):
        # Create and login a user
        User.objects.create_user(username=self.user_data['username'],
                                 email=self.user_data['email'],
                                 password=self.user_data['password'])

        data = {
            "email": "test@example.com",
            "password": "testpassword"
        }

        self.client.post(self.login_url, data)

        # Logout
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        self.assertEqual(response_data['message'], 'User logged out')

        # User authenticated mı diye kontrol eder.
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    """Test registration with missing required fields"""
"""""
    def test_register_missing_fields(self):
        incomplete_data = {
            'username': 'testuser',
            #'email': 'testexample2@gmail.com',
            'password': 'testpassword'
            # Missing email
        }

        response = self.client.post(self.register_url, incomplete_data)
        #print(response.json())
        self.assertEqual(response.status_code, 400)
"""""

# invalid email format unit testing yapmak istedik ama kod yok. @, gmail.com vs yazmadan hesap oluşturunca
# sıkıntı çıkmıyor

class AddressAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", email="email@example.com", password="password")

        # Force authentication for API testing
        self.client.force_login(self.user)

    def test_create_address(self):
        data = {
            "name": "Home",
            "street_address": "123 Test St",
            "city": "Testville",
            "state": "TS",
            "postal_code": "12345",
            "country": "Testland",
            "is_main": True
        }
        response = self.client.post("/addresses/", data, content_type="application/json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Address.objects.count(), 1)

    def test_get_addresses(self):
        Address.objects.create(user=self.user, name="Home", street_address="123 Test St", city="Testville", state="TS", postal_code="12345", country="Testland", is_main=True)

        response = self.client.get("/addresses/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_set_main_address(self):
        addr1 = Address.objects.create(user=self.user, name="Home", is_main=True)
        addr2 = Address.objects.create(user=self.user, name="Work", is_main=False)

        response = self.client.put(f"/addresses/{addr2.id}/set-main/", content_type="application/json")

        addr1.refresh_from_db()
        addr2.refresh_from_db()

        self.assertFalse(addr1.is_main)
        self.assertTrue(addr2.is_main)

    def test_delete_address(self):
        addr = Address.objects.create(user=self.user, name="Home")

        response = self.client.delete(f"/addresses/{addr.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(Address.objects.count(), 0)

    def test_get_multiple_addresses(self):
        # Create multiple addresses for the user
        Address.objects.create(user=self.user, name="Home", street_address="123 Test St", city="Testville", state="TS",
                               postal_code="12345", country="Testland", is_main=True)
        Address.objects.create(user=self.user, name="Work", street_address="456 Work St", city="Worktown", state="WT",
                               postal_code="67890", country="Testland", is_main=False)

        # Make GET request to retrieve all addresses
        response = self.client.get("/addresses/")

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)  # Ensure two addresses are returned




