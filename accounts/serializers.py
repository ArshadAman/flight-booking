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


class AdminCreateSupplierSerializer(serializers.Serializer):
    """Platform admin onboard supplier — same payload shape as AdminCreateAgentSerializer."""

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
    supplier_channel = serializers.CharField(max_length=32, required=False, allow_blank=True, default="B2B")
    supplier_class = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    aadhar = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    office_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    company_reg_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    operation_center = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    contact_designation = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    contact_mobile = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    bank_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    bank_account = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    branch_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    ifsc = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    country = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        if User.objects.filter(username__iexact=attrs["username"].strip()).exists():
            raise serializers.ValidationError({"username": "This login ID is already taken."})
        if User.objects.filter(email__iexact=attrs["email"].strip()).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})
        return attrs

    def create(self, validated_data):
        from agents.models import Supplier

        validated_data.pop("confirm_password")
        password = validated_data.pop("password")
        username = validated_data.pop("username").strip()
        email = validated_data.pop("email").strip().lower()
        company_name = (validated_data.pop("company_name", "") or "").strip()
        trade_name = (validated_data.pop("trade_name", "") or "").strip()
        first_name = validated_data.pop("first_name", "")
        last_name = validated_data.pop("last_name", "")
        phone_number = validated_data.pop("phone_number", "")

        extra = {k: validated_data.pop(k, "") for k in list(validated_data.keys())}

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=User.SUPPLIER,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            is_active=True,
        )
        contact = " ".join(p for p in [first_name, last_name] if p and str(p).strip()).strip()
        display_name = company_name or trade_name or contact or username
        registration = {
            "username": username,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
            "submitted_at": user.date_joined.isoformat() if user.date_joined else "",
        }
        supplier = Supplier.objects.create(
            name=display_name,
            contact_name=contact or username,
            email=email,
            phone=phone_number or extra.get("contact_mobile", "") or extra.get("office_phone", ""),
            status=Supplier.STATUS_APPROVED,
            portal_user=user,
            requested_by=user,
            notes=(extra.get("remark") or "").strip() or "Created by platform admin",
            integration_config={
                "registration": registration,
                "admin_onboard": extra,
            },
        )
        return supplier


class SupplierRegisterSerializer(serializers.ModelSerializer):
    """Same field set as AgentRegisterSerializer; creates pending supplier + inactive portal user."""

    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "password", "confirm_password", "first_name", "last_name", "phone_number")

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        username = (attrs.get("username") or "").strip()
        if username and User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError({"username": "This login ID is already taken."})
        email = (attrs.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        first = (validated_data.get("first_name") or "").strip()
        last = (validated_data.get("last_name") or "").strip()
        contact = " ".join(p for p in [first, last] if p).strip()
        validated_data["role"] = User.SUPPLIER
        validated_data["is_active"] = False
        user = User.objects.create_user(**validated_data)
        from agents.models import Supplier

        display_name = contact or user.username
        registration = {
            "username": user.username,
            "email": user.email or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "phone_number": user.phone_number or "",
            "submitted_at": user.date_joined.isoformat() if user.date_joined else "",
        }
        Supplier.objects.create(
            name=display_name,
            contact_name=contact or user.username,
            email=user.email or "",
            phone=user.phone_number or "",
            status=Supplier.STATUS_PENDING,
            requested_by=user,
            notes="Self-registration — pending admin approval",
            integration_config={"registration": registration},
        )
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
