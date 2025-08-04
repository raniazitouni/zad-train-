from djoser.serializers import (
    UserSerializer as BaseUserSerializer,
    UserCreateSerializer as BaseUserCreateSerializer,
    UserDeleteSerializer as BaseUserDeleteSerializer,
)
from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model


User = get_user_model()

class CustomUserDeleteSerializer(BaseUserDeleteSerializer):
    current_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        current_password = attrs.get('current_password')
        user = self.context['request'].user
        email = user.email

        if not authenticate(username=email, password=current_password):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})

        return attrs

    def delete(self):
        user = self.context['request'].user
        user.delete() 


class UserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        fields = ["id", "password", "email", "first_name", "last_name"]


class CustomUserSerializer(BaseUserSerializer):
    class Meta(BaseUserSerializer.Meta):
        fields = ["id", "email", "first_name", "last_name"]

