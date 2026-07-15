from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone_number', 'is_staff', 'is_superuser',
        )
        read_only_fields = ('id', 'role', 'is_staff', 'is_superuser')

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        # Do not allow clients to set `role` during registration; default to CUSTOMER.
        fields = ('username', 'email', 'password', 'confirm_password', 'first_name', 'last_name', 'phone_number')

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        # Force role to CUSTOMER for self-registered users
        validated_data['role'] = User.CUSTOMER
        user = User.objects.create_user(**validated_data)
        return user


class AgentRegisterSerializer(serializers.ModelSerializer):
    """
    Registration serializer for agents. Sets role = AGENT automatically.
    Requires the same fields as the customer register serializer plus
    an optional company_name / agency context field stored in last_name
    (or can be extended later with a dedicated profile model).
    """
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'confirm_password', 'first_name', 'last_name', 'phone_number')

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        # Always set role to AGENT for this endpoint
        validated_data['role'] = User.AGENT
        user = User.objects.create_user(**validated_data)
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Include user data in the response
        data.update({
            'user': {
                'id': str(self.user.id),
                'username': self.user.username,
                'email': self.user.email,
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
                'role': self.user.role,
                'is_staff': self.user.is_staff,
                'is_superuser': self.user.is_superuser,
            }
        })
        return data
