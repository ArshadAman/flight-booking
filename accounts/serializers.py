from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    wallet_balance = serializers.SerializerMethodField()
    wallet_currency = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone_number",
            "address_line",
            "city",
            "is_staff",
            "is_superuser",
            "wallet_balance",
            "wallet_currency",
        )
        read_only_fields = ("id", "role", "is_staff", "is_superuser", "wallet_balance", "wallet_currency")

    def _wallet(self, obj):
        try:
            from payments.views import get_or_create_wallet

            if getattr(obj, "role", "") == User.AGENT or getattr(obj, "is_staff", False):
                return get_or_create_wallet(obj)
        except Exception:
            return None
        return None

    def get_wallet_balance(self, obj):
        wallet = self._wallet(obj)
        return str(wallet.balance) if wallet else None

    def get_wallet_currency(self, obj):
        wallet = self._wallet(obj)
        return wallet.currency if wallet else None


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "password", "confirm_password", "first_name", "last_name", "phone_number")

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        validated_data["role"] = User.CUSTOMER
        user = User.objects.create_user(**validated_data)
        return user


class AgentRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "password", "confirm_password", "first_name", "last_name", "phone_number")

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        validated_data["role"] = User.AGENT
        user = User.objects.create_user(**validated_data)
        try:
            from payments.views import get_or_create_wallet

            get_or_create_wallet(user)
        except Exception:
            pass
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        wallet_balance = None
        wallet_currency = None
        try:
            from payments.views import get_or_create_wallet

            if self.user.role == User.AGENT or self.user.is_staff:
                wallet = get_or_create_wallet(self.user)
                wallet_balance = str(wallet.balance)
                wallet_currency = wallet.currency
        except Exception:
            pass
        data.update(
            {
                "user": {
                    "id": str(self.user.id),
                    "username": self.user.username,
                    "email": self.user.email,
                    "first_name": self.user.first_name,
                    "last_name": self.user.last_name,
                    "role": self.user.role,
                    "phone_number": self.user.phone_number,
                    "address_line": getattr(self.user, "address_line", ""),
                    "city": getattr(self.user, "city", ""),
                    "is_staff": self.user.is_staff,
                    "is_superuser": self.user.is_superuser,
                    "wallet_balance": wallet_balance,
                    "wallet_currency": wallet_currency,
                }
            }
        )
        return data
