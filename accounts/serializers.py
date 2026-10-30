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


class AdminCreateAgentSerializer(serializers.Serializer):
    """Platform admin creates a travel agency agent + company profile (no auto-login)."""

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    phone_number = serializers.CharField(max_length=15, required=False, allow_blank=True, default="")
    company_name = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    trade_name = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    gstin = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    pan = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    state = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    pincode = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    currency = serializers.CharField(max_length=8, required=False, allow_blank=True, default="INR")
    agent_channel = serializers.CharField(max_length=32, required=False, allow_blank=True, default="B2B")

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        if User.objects.filter(username__iexact=attrs["username"].strip()).exists():
            raise serializers.ValidationError({"username": "This login ID is already taken."})
        if User.objects.filter(email__iexact=attrs["email"].strip()).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        validated_data.pop("currency", None)
        validated_data.pop("agent_channel", None)
        profile_fields = {
            "company_name": validated_data.pop("company_name", ""),
            "trade_name": validated_data.pop("trade_name", ""),
            "address": validated_data.pop("address", ""),
            "gstin": validated_data.pop("gstin", ""),
            "pan": validated_data.pop("pan", ""),
            "city": validated_data.pop("city", ""),
            "state": validated_data.pop("state", ""),
            "pincode": validated_data.pop("pincode", ""),
        }
        password = validated_data.pop("password")
        username = validated_data.pop("username").strip()
        email = validated_data.pop("email").strip()
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=User.AGENT,
            first_name=validated_data.pop("first_name", ""),
            last_name=validated_data.pop("last_name", ""),
            phone_number=validated_data.pop("phone_number", ""),
        )
        try:
            from payments.views import get_or_create_wallet

            get_or_create_wallet(user)
        except Exception:
            pass
        from agents.models import CompanyProfile, InvoiceSetting

        profile_fields["email"] = email
        profile_fields["phone"] = user.phone_number or ""
        CompanyProfile.objects.update_or_create(agent=user, defaults=profile_fields)
        InvoiceSetting.objects.get_or_create(agent=user)
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
        # UI accepts "username or email" — resolve email to username before JWT auth.
        login_id = (attrs.get(self.username_field) or "").strip()
        if login_id and "@" in login_id:
            matched = User.objects.filter(email__iexact=login_id).first()
            if matched:
                attrs[self.username_field] = matched.username
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
