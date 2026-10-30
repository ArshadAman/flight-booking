from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AgentDashboardAPITests(APITestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username="dash_agent",
            email="dash@agent.com",
            password="pass12345",
            role=User.AGENT,
        )
        self.admin = User.objects.create_user(
            username="dash_admin",
            email="dash@admin.com",
            password="pass12345",
            role=User.ADMIN,
        )

    def test_agent_dashboard_returns_kpi_shape(self):
        self.client.force_authenticate(user=self.agent)
        url = reverse("agent-dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        data = body.get("data", body)
        self.assertIn("kpi", data)
        self.assertIn("total_booking", data["kpi"])
        self.assertIn("wallet_balance", data["kpi"])
        self.assertIn("quick_actions", data)
        self.assertTrue(any(a.get("href") for a in data["quick_actions"]))

    def test_platform_admin_dashboard_sees_aggregate_fields(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("agent-dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        data = body.get("data", body)
        self.assertIn("top_agents", data)
        self.assertIn("top_airlines", data)

    def test_unauthenticated_dashboard_rejected(self):
        url = reverse("agent-dashboard")
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
