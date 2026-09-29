from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.consts import TYPES_DICT
from home.models import Box, OriginalTrainer, PersonalDex, Slot, Specimen
from pokedex.models import PokemonForm, Version
from pokedex.renderers import HomeSpriteRenderer


def absolute_url(request, path) -> str:
    url = path.as_posix()
    return request.build_absolute_uri(url) if request else url


def form_sprite_url(request, form: PokemonForm, shiny: bool) -> str | None:
    if form.pokemon is None:
        return None

    renderer = HomeSpriteRenderer(form, "shiny" if shiny else "default")
    return absolute_url(request, renderer.resolve_sprite_url())


def pokeball_sprite_url(request, pokeball: str | None) -> str | None:
    if not pokeball:
        return None

    return absolute_url(request, settings.ITEM_SPRITES_URL / f"{pokeball}.png")


class FormRefSerializer(serializers.ModelSerializer):
    """Requer ``select_related("pokemon__species")`` na queryset."""

    sprite_url = serializers.SerializerMethodField()
    shiny_sprite_url = serializers.SerializerMethodField()

    class Meta:
        model = PokemonForm
        fields: tuple[str, ...] = (
            "id",
            "name",
            "form_name",
            "pokeapi_id",
            "sprite_url",
            "shiny_sprite_url",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_sprite_url(self, obj: PokemonForm) -> str | None:
        return form_sprite_url(self.context.get("request"), obj, shiny=False)

    @extend_schema_field(OpenApiTypes.URI)
    def get_shiny_sprite_url(self, obj: PokemonForm) -> str | None:
        return form_sprite_url(self.context.get("request"), obj, shiny=True)


def type_sprite_url(request, type_: str) -> str | None:
    """Ícone pequeno (60×60) do tipo, ou ``None`` se não houver arquivo."""
    type_id = TYPES_DICT.get(type_)
    if type_id is None:
        return None

    relative = (
        Path(settings.TYPE_SPRITES_DEFAULT_GEN)
        / settings.TYPE_SPRITES_DEFAULT_GAME
        / "small"
        / f"{type_id}.png"
    )
    if not (settings.TYPE_SPRITES_ROOT / relative).is_file():
        return None

    return absolute_url(request, settings.TYPE_SPRITES_URL / relative)


class FormTypeSerializer(serializers.Serializer):
    slot = serializers.IntegerField()
    type = serializers.CharField()
    sprite_url = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.URI)
    def get_sprite_url(self, obj) -> str | None:
        return type_sprite_url(self.context.get("request"), obj.type)


class FormAbilitySerializer(serializers.Serializer):
    slot = serializers.IntegerField()
    ability = serializers.CharField()
    is_hidden = serializers.BooleanField()


class FormDetailSerializer(FormRefSerializer):
    types = serializers.SerializerMethodField()
    abilities = serializers.SerializerMethodField()
    is_shinylocked = serializers.BooleanField(read_only=True)
    is_distro_only = serializers.BooleanField(read_only=True)

    class Meta(FormRefSerializer.Meta):
        fields = FormRefSerializer.Meta.fields + (
            "types",
            "abilities",
            "is_shinylocked",
            "is_distro_only",
        )

    @extend_schema_field(FormTypeSerializer(many=True))
    def get_types(self, obj: PokemonForm):
        types = sorted(obj.types.all(), key=lambda t: t.slot)
        return FormTypeSerializer(types, many=True, context=self.context).data

    @extend_schema_field(FormAbilitySerializer(many=True))
    def get_abilities(self, obj: PokemonForm):
        if obj.pokemon is None:
            return []

        abilities = sorted(obj.pokemon.abilities.all(), key=lambda a: a.slot)
        return FormAbilitySerializer(abilities, many=True).data


class SpecimenSummarySerializer(serializers.ModelSerializer):
    pokeball_sprite_url = serializers.SerializerMethodField()

    class Meta:
        model = Specimen
        fields = (
            "id",
            "nickname",
            "form_name",
            "ability",
            "is_shiny",
            "is_alpha",
            "pokeball",
            "pokeball_sprite_url",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_pokeball_sprite_url(self, obj: Specimen) -> str | None:
        return pokeball_sprite_url(self.context.get("request"), obj.pokeball)


class SpecimenSerializer(serializers.ModelSerializer):
    """Specimen completo.

    ``form`` é escrito pelo id; ``form_ref`` é a representação somente leitura.
    ``slot`` é o id do slot onde o specimen está depositado (anotado na view).
    """

    form_ref = FormRefSerializer(source="form", read_only=True)
    pokeball_sprite_url = serializers.SerializerMethodField()
    slot = serializers.IntegerField(source="slot_id", read_only=True, allow_null=True)

    class Meta:
        model = Specimen
        fields = "__all__"

    @extend_schema_field(OpenApiTypes.URI)
    def get_pokeball_sprite_url(self, obj: Specimen) -> str | None:
        return pokeball_sprite_url(self.context.get("request"), obj.pokeball)

    def to_representation(self, instance):
        # Após create/update a instância não vem da queryset anotada.
        if not hasattr(instance, "slot_id"):
            slot = Slot.objects.filter(specimen=instance).only("pk").first()
            instance.slot_id = slot.pk if slot else None

        return super().to_representation(instance)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # A forma é fixa: trocá-la num specimen depositado quebraria a regra
        # de Slot.clean (forma do specimen = forma do slot).
        if self.instance and "form" in attrs and attrs["form"] != self.instance.form:
            raise serializers.ValidationError(
                {"form": [_("the form of a specimen can't be changed.")]}
            )

        form = attrs.get("form", getattr(self.instance, "form", None))
        ability = attrs.get("ability", getattr(self.instance, "ability", None))

        # Mesma regra do SpecimenAdminForm: a ability deve ser uma das
        # abilities do pokémon da forma.
        if ability and form is not None:
            abilities = (
                set(form.pokemon.abilities.values_list("ability", flat=True))
                if form.pokemon
                else set()
            )

            if ability not in abilities:
                raise serializers.ValidationError(
                    {
                        "ability": [
                            _("“%(ability)s” is not a valid ability for %(form)s.")
                            % {"ability": ability, "form": form.name}
                        ]
                    }
                )

        return attrs


class BoxRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Box
        fields: tuple[str, ...] = ("id", "name", "position")


class BoxSummarySerializer(BoxRefSerializer):
    total = serializers.IntegerField(read_only=True)
    registered = serializers.IntegerField(read_only=True)

    class Meta(BoxRefSerializer.Meta):
        fields = BoxRefSerializer.Meta.fields + ("total", "registered")


class SlotSerializer(serializers.ModelSerializer):
    """Requer ``select_related`` de box, personal_dex, specimen e
    form__pokemon__species na queryset."""

    box = BoxRefSerializer(read_only=True)
    form = FormRefSerializer(read_only=True, allow_null=True)
    specimen = SpecimenSummarySerializer(read_only=True, allow_null=True)
    is_shiny_display = serializers.SerializerMethodField()

    class Meta:
        model = Slot
        fields = (
            "id",
            "box",
            "row",
            "col",
            "personal_dex",
            "form",
            "specimen",
            "is_shiny_display",
        )

    def get_is_shiny_display(self, obj: Slot) -> bool:
        if obj.specimen is not None:
            return obj.specimen.is_shiny

        return bool(obj.form and obj.personal_dex and obj.personal_dex.is_shiny_dex)


class PersonalDexSerializer(serializers.ModelSerializer):
    total = serializers.IntegerField(read_only=True)
    registered = serializers.IntegerField(read_only=True)

    class Meta:
        model = PersonalDex
        fields = (
            "id",
            "name",
            "is_shiny_dex",
            "force_new_box",
            "total",
            "registered",
        )


class PersonalDexCreateSerializer(serializers.ModelSerializer):
    """Dados para criar um PersonalDex com o conjunto padrão de formas."""

    class Meta:
        model = PersonalDex
        fields = ("name", "is_shiny_dex", "force_new_box")


class PersonalDexPreviewSerializer(serializers.Serializer):
    """Simulação de um dex padrão: o que seria criado, sem criar nada."""

    forms = serializers.IntegerField()
    boxes_needed = serializers.IntegerField()
    largest_free_run = serializers.IntegerField()
    enough_space = serializers.BooleanField()
    first_box = BoxRefSerializer(allow_null=True)


class DepositSerializer(serializers.Serializer):
    """Valida o depósito de um specimen no slot passado em ``context["slot"]``.

    A queryset do specimen usa ``select_for_update``: a validação deve rodar
    dentro de ``transaction.atomic``.
    """

    specimen_id = serializers.PrimaryKeyRelatedField(
        queryset=Specimen.objects.select_for_update()
    )

    def validate(self, attrs):
        slot: Slot = self.context["slot"]
        specimen: Specimen = attrs["specimen_id"]

        if slot.form_id is None:
            raise serializers.ValidationError(
                _("this slot has no form; specimens can't be deposited in it.")
            )

        slot.specimen = specimen

        try:
            slot.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                {"specimen_id": e.message_dict.get("specimen", e.messages)}
            )

        if Slot.objects.filter(specimen=specimen).exclude(pk=slot.pk).exists():
            raise serializers.ValidationError(
                {
                    "specimen_id": [
                        _("this specimen is already deposited in another slot.")
                    ]
                }
            )

        return attrs


class GenerationProgressSerializer(serializers.Serializer):
    """Progresso de um PersonalDex numa geração (``null`` = formas sem
    pokémon associado)."""

    generation = serializers.CharField(allow_null=True)
    total = serializers.IntegerField()
    registered = serializers.IntegerField()
    first_box = BoxRefSerializer()


class VersionSerializer(serializers.ModelSerializer):
    """Versão de jogo, para o treinador original (``OriginalTrainer.version``).

    Requer ``select_related("version_group")`` na queryset.
    """

    version_group = serializers.CharField(source="version_group.name")
    generation = serializers.CharField(source="version_group.generation")

    class Meta:
        model = Version
        fields = ("name", "version_group", "generation")


class TrainerSerializer(serializers.ModelSerializer):
    version = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Version.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = OriginalTrainer
        fields = ("id", "name", "trainer_id", "version")


class ChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class PokeballChoiceSerializer(ChoiceSerializer):
    sprite_url = serializers.CharField()


class SpecimenOptionsSerializer(serializers.Serializer):
    language = ChoiceSerializer(many=True)
    gender = ChoiceSerializer(many=True)
    nature = ChoiceSerializer(many=True)
    pokeball = PokeballChoiceSerializer(many=True)
