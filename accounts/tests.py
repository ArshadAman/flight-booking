from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthenticationTests(APITestCase):
    def test_user_registration(self):
        url = reverse('auth_register')
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "first_name": "Test",
            "last_name": "User",
            "role": "CUSTOMER"
        }
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.count() == 1
        assert User.objects.get().username == "testuser"

    def test_user_login(self):
        # Create user
        User.objects.create_user(username="testuser", password="password123", email="test@example.com")
        
        url = reverse('token_obtain_pair')
        data = {
            "username": "testuser",
            "password": "password123"
        }
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_profile_access(self):
        user = User.objects.create_user(username="testuser", password="password123", email="test@example.com")
        self.client.force_authenticate(user=user)
        
        url = reverse('auth_profile')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == "testuser"
