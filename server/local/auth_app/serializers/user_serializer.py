from rest_framework import serializers

class RegisterUserSerializer(serializers.Serializer):
    company = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['manager', 'user'])

class UpdateUserSerializer(serializers.Serializer):
    company = serializers.CharField(required=False)
    name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, required=False)
    role = serializers.ChoiceField(choices=['manager', 'user'], required=False)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
