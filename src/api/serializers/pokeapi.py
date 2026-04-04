from rest_framework import serializers


class NamedAPIResourceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    url = serializers.CharField(max_length=200)


class EncounterSerializer(serializers.Serializer):
    min_level = serializers.IntegerField()
    max_level = serializers.IntegerField()
    condition_values = NamedAPIResourceSerializer(many=True)
    chance = serializers.IntegerField()
    method = NamedAPIResourceSerializer()


class VersionEncounterDetailSerializer(serializers.Serializer):
    version = NamedAPIResourceSerializer()
    max_chance = serializers.IntegerField()
    encounter_details = EncounterSerializer(many=True)


class VersionNameIndexSerializer(serializers.Serializer):
    game_index = serializers.IntegerField()
    version = NamedAPIResourceSerializer()


class PokemonAbilitySerializer(serializers.Serializer):
    is_hidden = serializers.BooleanField()
    slot = serializers.IntegerField()
    ability = NamedAPIResourceSerializer()


class PokemonHeldItemVersionSerializer(serializers.Serializer):
    version = NamedAPIResourceSerializer()
    rarity = serializers.IntegerField()


class PokemonHeldItemSerializer(serializers.Serializer):
    item = NamedAPIResourceSerializer()
    version_details = PokemonHeldItemVersionSerializer(many=True)


class PokemonLocationAreasSerializer(serializers.Serializer):
    location_area = NamedAPIResourceSerializer()
    version_details = VersionEncounterDetailSerializer(many=True)


class PokemonMoveVersionSerializer(serializers.Serializer):
    move_learn_method = NamedAPIResourceSerializer()
    version_group = NamedAPIResourceSerializer()
    level_learned_at = serializers.IntegerField()
    order = serializers.IntegerField()


class PokemonMoveSerializer(serializers.Serializer):
    move = NamedAPIResourceSerializer()
    version_group_details = PokemonMoveVersionSerializer(many=True)


class PokemonTypeSerializer(serializers.Serializer):
    slot = serializers.IntegerField()
    type = NamedAPIResourceSerializer()


class PokemonTypePastSerializer(serializers.Serializer):
    generation = NamedAPIResourceSerializer()
    types = PokemonTypeSerializer(many=True)


class PokemonAbilityPastSerializer(serializers.Serializer):
    generation = NamedAPIResourceSerializer()
    abilities = PokemonAbilitySerializer(many=True)


class PokemonStatSerializer(serializers.Serializer):
    stat = NamedAPIResourceSerializer()
    effort = serializers.IntegerField()
    base_stat = serializers.IntegerField()


class PokemonStatPastSerializer(serializers.Serializer):
    generation = NamedAPIResourceSerializer()
    stats = PokemonStatSerializer(many=True)


class PokemonSpritesSerializer(serializers.Serializer):
    front_default = serializers.CharField(max_length=200)
    front_shiny = serializers.CharField(max_length=200)
    front_female = serializers.CharField(max_length=200)
    front_shiny_female = serializers.CharField(max_length=200)
    back_default = serializers.CharField(max_length=200)
    back_shiny = serializers.CharField(max_length=200)
    back_female = serializers.CharField(max_length=200)
    back_shiny_female = serializers.CharField(max_length=200)


class PokemonCriesSerializer(serializers.Serializer):
    latest = serializers.CharField(max_length=200)
    legacy = serializers.CharField(max_length=200)


class PokemonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=200)
    height = serializers.IntegerField()
    base_experience = serializers.IntegerField()
    is_default = serializers.BooleanField()
    order = serializers.IntegerField()
    weight = serializers.IntegerField()
    abilities = PokemonAbilitySerializer(many=True)
    forms = NamedAPIResourceSerializer(many=True)
    game_indices = VersionNameIndexSerializer(many=True)
    held_items = PokemonHeldItemSerializer(many=True)
    location_area_encounters = PokemonLocationAreasSerializer(many=True)
    moves = PokemonMoveSerializer(many=True)
    past_types = PokemonTypePastSerializer(many=True)
    past_abilities = PokemonAbilityPastSerializer(many=True)
    past_stats = PokemonStatPastSerializer(many=True)
    sprites = PokemonSpritesSerializer()
    cries = PokemonCriesSerializer()
    species = NamedAPIResourceSerializer()
    stats = PokemonStatSerializer(many=True)
    types = PokemonTypeSerializer(many=True)
    types = PokemonTypeSerializer(many=True)
