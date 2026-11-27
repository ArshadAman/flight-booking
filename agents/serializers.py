from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import (
    InventoryRestriction,
    AgentAuditLog,
    Supplier,
    Notice,
    AgentCommission,
    Discount,
    MarkupRule,
    ServiceCharge,
    StaffMember,
    CompanyProfile,
    InvoiceSetting,
)

User = get_user_model()


class InventoryRestrictionSerializer(serializers.ModelSerializer):
    agent_username = serializers.CharField(source="agent.username", read_only=True, allow_null=True)

    class Meta:
        model = InventoryRestriction
        fields = [
            "id",
            "agent",
            "agent_username",
            "scope",
            "airline_code",
            "airline_name",
            "origin",
            "destination",
            "is_blocked",
            "reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "agent_username"]

    def validate(self, attrs):
        scope = attrs.get("scope") or getattr(self.instance, "scope", None)
        airline = (attrs.get("airline_code") or getattr(self.instance, "airline_code", "") or "").strip().upper()
        origin = (attrs.get("origin") or getattr(self.instance, "origin", "") or "").strip().upper()
        dest = (attrs.get("destination") or getattr(self.instance, "destination", "") or "").strip().upper()

        if "airline_code" in attrs:
            attrs["airline_code"] = airline
        if "origin" in attrs:
            attrs["origin"] = origin
        if "destination" in attrs:
            attrs["destination"] = dest

        if scope == InventoryRestriction.SCOPE_AIRLINE and not airline:
            raise serializers.ValidationError({"airline_code": "Airline code is required for airline blocks."})
        if scope == InventoryRestriction.SCOPE_ROUTE and (not origin or not dest):
            raise serializers.ValidationError({"origin": "Origin and destination are required for route blocks."})
        return attrs


class SupplierRegistrationDetailsSerializer(serializers.Serializer):
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    submitted_at = serializers.CharField(read_only=True, required=False, allow_blank=True)


class SupplierSerializer(serializers.ModelSerializer):
    portal_username = serializers.SerializerMethodField()
    portal_is_active = serializers.SerializerMethodField()
    registration_details = serializers.SerializerMethodField()
    registration = SupplierRegistrationDetailsSerializer(required=False, write_only=True)

    class Meta:
        model = Supplier
        fields = (
            "id",
            "code",
            "name",
            "contact_name",
            "email",
            "phone",
            "status",
            "inventory_count",
            "notes",
            "integration_config",
            "portal_username",
            "portal_is_active",
            "registration_details",
            "registration",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "code", "portal_username", "portal_is_active", "registration_details", "created_at", "updated_at")

    def get_portal_username(self, obj):
        if obj.portal_user_id and obj.portal_user:
            return obj.portal_user.username
        return None

    def get_portal_is_active(self, obj):
        if obj.portal_user_id and obj.portal_user is not None:
            return bool(obj.portal_user.is_active)
        if obj.requested_by_id and obj.requested_by is not None:
            return bool(obj.requested_by.is_active)
        return None

    def get_registration_details(self, obj):
        cfg = (obj.integration_config or {}).get("registration") or {}
        user = obj.portal_user or obj.requested_by
        live = {}
        if user:
            live = {
                "username": user.username,
                "email": user.email or "",
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "phone_number": user.phone_number or "",
            }
        merged = {**cfg, **{k: v for k, v in live.items() if v is not None and v != ""}}
        if not merged.get("submitted_at") and obj.created_at:
            merged["submitted_at"] = obj.created_at.isoformat()
        return merged

    def _sync_registration_user(self, instance, reg: dict):
        if not reg:
            return
        user = instance.portal_user or instance.requested_by
        if not user:
            return
        user_fields = {}
        if "first_name" in reg:
            user_fields["first_name"] = (reg.get("first_name") or "").strip()
        if "last_name" in reg:
            user_fields["last_name"] = (reg.get("last_name") or "").strip()
        if "phone_number" in reg:
            user_fields["phone_number"] = (reg.get("phone_number") or "").strip()
        if "email" in reg and (reg.get("email") or "").strip():
            user_fields["email"] = (reg.get("email") or "").strip().lower()
        if user_fields:
            for k, v in user_fields.items():
                setattr(user, k, v)
            user.save(update_fields=[*user_fields.keys(), "updated_at"])
        if "first_name" in reg or "last_name" in reg:
            contact = " ".join(
                p for p in [user.first_name, user.last_name] if p and str(p).strip()
            ).strip()
            if contact:
                instance.contact_name = contact
        if "email" in reg:
            instance.email = user_fields.get("email", instance.email)
        if "phone_number" in reg:
            instance.phone = user_fields.get("phone_number", instance.phone)
        cfg = dict(instance.integration_config or {})
        snapshot = dict(cfg.get("registration") or {})
        snapshot.update(
            {
                "username": user.username,
                "email": user.email or "",
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "phone_number": user.phone_number or "",
            }
        )
        cfg["registration"] = snapshot
        instance.integration_config = cfg

    def update(self, instance, validated_data):
        reg = validated_data.pop("registration", None)
        instance = super().update(instance, validated_data)
        request = self.context.get("request")
        if request and reg is not None:
            from accounts.permissions import is_platform_admin

            if is_platform_admin(request.user):
                self._sync_registration_user(instance, reg)
                instance.save(
                    update_fields=[
                        "contact_name",
                        "email",
                        "phone",
                        "integration_config",
                        "updated_at",
                    ]
                )
        return instance


class AgentAuditLogSerializer(serializers.ModelSerializer):
    by_agent = serializers.SerializerMethodField()

    class Meta:
        model = AgentAuditLog
        fields = (
            "id",
            "action_type",
            "entry",
            "reference",
            "metadata",
            "by_agent",
            "created_at",
        )
        read_only_fields = fields

    def get_by_agent(self, obj):
        user = obj.performed_by or obj.agent
        if not user:
            return "AGT"
        base = "".join(ch for ch in f"{user.first_name}{user.last_name}{user.username}" if ch.isalpha())
        return (base.upper()[:3] or "AGT")


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ("id", "category", "label", "title", "body", "is_active", "created_at")
        read_only_fields = ("id", "created_at")


class AgentCommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentCommission
        fields = ("id", "category", "method", "markup", "updated_at")
        read_only_fields = ("id", "updated_at")


class DiscountSerializer(serializers.ModelSerializer):
    agent = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Discount
        fields = (
            "id",
            "agent",
            "code",
            "title",
            "discount_type",
            "value",
            "min_booking",
            "max_discount",
            "valid_until",
            "usage_count",
            "usage_limit",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "usage_count", "created_at")


class MarkupRuleSerializer(serializers.ModelSerializer):
    agent = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = MarkupRule
        fields = (
            "id",
            "agent",
            "channel",
            "airline",
            "sector",
            "markup_type",
            "value",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class ServiceChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCharge
        fields = (
            "id",
            "code",
            "name",
            "charge_type",
            "amount",
            "gst_rate",
            "apply_on",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class StaffMemberSerializer(serializers.ModelSerializer):
    agent_id = serializers.UUIDField(source="agent.id", read_only=True)
    agent_username = serializers.CharField(source="agent.username", read_only=True)
    agent_email = serializers.EmailField(source="agent.email", read_only=True)

    class Meta:
        model = StaffMember
        fields = (
            "id",
            "agent_id",
            "agent_username",
            "agent_email",
            "name",
            "email",
            "phone",
            "role",
            "status",
            "bookings_count",
            "total_sales",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class CompanyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = (
            "id",
            "company_name",
            "trade_name",
            "iata_number",
            "gstin",
            "pan",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "pincode",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at")


class InvoiceSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSetting
        fields = (
            "id",
            "series_prefix",
            "starting_seq",
            "current_seq",
            "show_tax_breakdown",
            "show_airline_pnr",
            "footer_note",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at")
