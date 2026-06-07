from rest_framework import serializers
from bookings.models import GroupBooking, GroupQuote, GroupPassenger, GroupChangeRequest
from django.contrib.auth import get_user_model

User = get_user_model()

class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']


class GroupQuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupQuote
        fields = '__all__'
        read_only_fields = ['id', 'booking', 'created_at', 'updated_at']


class GroupPassengerSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupPassenger
        fields = '__all__'
        read_only_fields = ['id', 'booking', 'created_at', 'updated_at']


class GroupChangeRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupChangeRequest
        fields = '__all__'
        read_only_fields = ['id', 'booking', 'change_request_id', 'created_at', 'updated_at']


class GroupBookingSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    quotes = GroupQuoteSerializer(many=True, read_only=True)
    passengers = GroupPassengerSerializer(many=True, read_only=True)
    change_requests = GroupChangeRequestSerializer(many=True, read_only=True)

    class Meta:
        model = GroupBooking
        fields = '__all__'
        read_only_fields = [
            'id', 'request_id', 'status', 'user', 'total_paid', 
            'payment_deadline', 'balance_deadline', 'created_at', 'updated_at'
        ]
