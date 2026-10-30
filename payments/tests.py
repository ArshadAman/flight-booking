from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class PlatformAgentAdminAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="platform_admin",
            email="admin@platform.com",
            password="pass12345",
            role=User.ADMIN,
        )
        self.agent = User.objects.create_user(
            username="existing_agent",
            email="agent@existing.com",
            password="pass12345",
            role=User.AGENT,
        )

    def test_admin_can_create_agent(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("platform-agents")
        payload = {
            "username": "new_agency_01",
            "email": "new@agency.com",
            "password": "SecurePass1!",
            "confirm_password": "SecurePass1!",
            "first_name": "Ravi",
            "last_name": "Travels",
            "phone_number": "9876543210",
            "company_name": "Ravi Travels Pvt Ltd",
            "trade_name": "Ravi Fly",
            "city": "Delhi",
            "state": "Delhi",
            "pincode": "110001",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], "new_agency_01")
        created = User.objects.get(username="new_agency_01")
        self.assertEqual(created.role, User.AGENT)
        self.assertTrue(hasattr(created, "company_profile"))

    def test_non_admin_cannot_create_agent(self):
        self.client.force_authenticate(user=self.agent)
        url = reverse("platform-agents")
        response = self.client.post(
            url,
            {
                "username": "blocked",
                "email": "blocked@x.com",
                "password": "SecurePass1!",
                "confirm_password": "SecurePass1!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
