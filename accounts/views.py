from rest_framework import generics, status, permissions
from rest_framework.response import Response
from .serializers import UserSerializer, RegisterSerializer, AgentRegisterSerializer, CustomTokenObtainPairSerializer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data
        return Response(
            {
                "user": user_data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class AgentRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = AgentRegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data
        return Response(
            {
                "user": user_data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        user = self.get_object()
        before = {
            "phone_number": user.phone_number or "",
            "address_line": getattr(user, "address_line", "") or "",
            "city": getattr(user, "city", "") or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "email": user.email or "",
        }
        updated = serializer.save()
        try:
            from agents.models import AgentAuditLog, log_agent_action

            after = {
                "phone_number": updated.phone_number or "",
                "address_line": getattr(updated, "address_line", "") or "",
                "city": getattr(updated, "city", "") or "",
                "first_name": updated.first_name or "",
                "last_name": updated.last_name or "",
                "email": updated.email or "",
            }
            if before["phone_number"] != after["phone_number"]:
                log_agent_action(
                    agent=updated,
                    performed_by=updated,
                    action_type=AgentAuditLog.ACTION_PROFILE,
                    entry="Contact Number Changed",
                )
            if before["address_line"] != after["address_line"] or before["city"] != after["city"]:
                log_agent_action(
                    agent=updated,
                    performed_by=updated,
                    action_type=AgentAuditLog.ACTION_PROFILE,
                    entry="Address Changed",
                )
            if before["first_name"] != after["first_name"] or before["last_name"] != after["last_name"]:
                log_agent_action(
                    agent=updated,
                    performed_by=updated,
                    action_type=AgentAuditLog.ACTION_PROFILE,
                    entry="Name Changed",
                )
            if before["email"] != after["email"]:
                log_agent_action(
                    agent=updated,
                    performed_by=updated,
                    action_type=AgentAuditLog.ACTION_PROFILE,
                    entry="Email Changed",
                )
        except Exception:
            pass
