from rest_framework import serializers

from .models import FediActor, FediFollower, FediActivity, FediDelivery


class FediActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = FediActor
        fields = "__all__"


class FediFollowerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FediFollower
        fields = "__all__"


class FediActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = FediActivity
        fields = "__all__"


class FediDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = FediDelivery
        fields = "__all__"

