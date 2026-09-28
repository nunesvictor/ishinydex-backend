from rest_framework import serializers

from pokedex.models import Pokemon, PokemonAbility, PokemonStat, PokemonType

# Ordem canônica da PokéAPI, usada no gráfico de stats base.
STAT_ORDER = (
    "hp",
    "attack",
    "defense",
    "special-attack",
    "special-defense",
    "speed",
)


class PokemonAbilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PokemonAbility
        fields = ("slot", "ability", "is_hidden")


class PokemonStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = PokemonStat
        fields = ("stat", "base_stat", "effort")


class PokemonTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PokemonType
        fields = ("slot", "type")


class PokemonSerializer(serializers.ModelSerializer):
    abilities = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    types = serializers.SerializerMethodField()

    class Meta:
        model = Pokemon
        exclude = (
            "game_indices",
            "moves",
        )

    # Ordenação em Python: usa o prefetch da view sem consultas extras.
    def get_abilities(self, obj: Pokemon):
        abilities = sorted(obj.abilities.all(), key=lambda a: a.slot)
        return PokemonAbilitySerializer(abilities, many=True).data

    def get_stats(self, obj: Pokemon):
        def position(stat: PokemonStat) -> int:
            try:
                return STAT_ORDER.index(stat.stat)
            except ValueError:
                return len(STAT_ORDER)

        stats = sorted(obj.stats.all(), key=position)
        return PokemonStatSerializer(stats, many=True).data

    def get_types(self, obj: Pokemon):
        types = sorted(obj.types.all(), key=lambda t: t.slot)
        return PokemonTypeSerializer(types, many=True).data
