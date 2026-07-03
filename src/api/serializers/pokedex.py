from rest_framework import serializers

from pokedex.models import Pokemon


class PokemonSerializer(serializers.ModelSerializer):
    abilities = serializers.StringRelatedField(many=True)
    stats = serializers.StringRelatedField(many=True)
    types = serializers.StringRelatedField(many=True)

    class Meta:
        model = Pokemon
        exclude = (
            "game_indices",
            "moves",
        )
