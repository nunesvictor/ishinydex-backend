from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.consts import TYPES_DICT
from home.models import (
    HOME_TRANSFER_VERSIONS,
    Box,
    OriginalTrainer,
    PersonalDex,
    Save,
    Slot,
    Specimen,
)
from home.origin_marks import ORIGIN_MARK_LABELS
from home.services import allowed_genders, with_origin_version
from pokedex.models import PokemonForm, PokemonSpeciesDexEntry, ShinyLock, Version
from pokedex.renderers import HomeSpriteRenderer

from ..filters import HUNT_REASONS


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


def national_number_prefetch(prefix: str = "") -> Prefetch:
    """Prefetch do nº da Pokédex nacional lido por ``FormRefSerializer``;
    ``prefix`` é o caminho até a forma (ex.: ``"form__"``)."""
    return Prefetch(
        f"{prefix}pokemon__species__pokedex_numbers",
        queryset=PokemonSpeciesDexEntry.objects.filter(pokedex="national"),
        to_attr="national_entries",
    )


class FormRefSerializer(serializers.ModelSerializer):
    """Requer ``select_related("pokemon__species")`` e
    ``national_number_prefetch`` na queryset (sem o prefetch, uma consulta
    por forma)."""

    national_number = serializers.SerializerMethodField()
    sprite_url = serializers.SerializerMethodField()
    shiny_sprite_url = serializers.SerializerMethodField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = PokemonForm
        fields: tuple[str, ...] = (
            "id",
            "name",
            "form_name",
            "pokeapi_id",
            "national_number",
            "sprite_url",
            "shiny_sprite_url",
        )

    def get_national_number(self, obj: PokemonForm) -> int | None:
        species = obj.pokemon.species if obj.pokemon else None
        if species is None:
            return None

        entries = getattr(species, "national_entries", None)
        if entries is None:
            entries = species.pokedex_numbers.filter(pokedex="national")

        return next((entry.entry_number for entry in entries), None)

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


class TrainerSerializer(serializers.ModelSerializer):
    version = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Version.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = OriginalTrainer
        fields = ("id", "name", "trainer_id", "version")


class SaveRefSerializer(serializers.ModelSerializer):
    """Save do usuário, com o treinador completo (somente leitura)."""

    trainer = TrainerSerializer(read_only=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Save
        fields = ("id", "label", "trainer")


class SaveSerializer(serializers.ModelSerializer):
    """Cria/edita um save: ``trainer`` pelo id (fixo depois de criado). A
    resposta é um ``SaveRefSerializer``."""

    trainer = serializers.PrimaryKeyRelatedField(
        queryset=OriginalTrainer.objects.select_related("version")
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Save
        fields = ("id", "label", "trainer")

    def to_representation(self, instance):
        return SaveRefSerializer(instance).data

    def validate_trainer(self, trainer: OriginalTrainer) -> OriginalTrainer:
        if self.instance and trainer != self.instance.trainer:
            raise serializers.ValidationError(
                _("the trainer of a save can't be changed.")
            )

        version = trainer.version
        if version is None or version.name not in HOME_TRANSFER_VERSIONS:
            raise serializers.ValidationError(
                _(
                    "only trainers from games that receive Pokémon from HOME "
                    "can be saves."
                )
            )

        if not self.instance and Save.objects.filter(trainer=trainer).exists():
            raise serializers.ValidationError(_("this trainer is already a save."))

        return trainer


class SpecimenSummarySerializer(serializers.ModelSerializer):
    pokeball_sprite_url = serializers.SerializerMethodField()
    location = SaveRefSerializer(read_only=True, allow_null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Specimen
        fields = (
            "id",
            "nickname",
            "form_name",
            "ability",
            "is_shiny",
            "is_alpha",
            "is_from_go",
            "gender",
            "pokeball",
            "pokeball_sprite_url",
            "location",
            "location_since",
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
    # Derivados do OT (ver home.origin_marks): nunca escritos pela API.
    origin_version = serializers.SlugRelatedField(slug_field="name", read_only=True)
    origin_mark = serializers.ChoiceField(
        choices=list(ORIGIN_MARK_LABELS), read_only=True, allow_null=True
    )
    # Só muda por POST /specimens/transfer/.
    location = SaveRefSerializer(read_only=True, allow_null=True)
    location_since = serializers.DateField(read_only=True, allow_null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
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

        # A ability deve ser uma das abilities do pokémon da forma.
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
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Box
        fields: tuple[str, ...] = ("id", "name", "position")


class BoxSummarySerializer(BoxRefSerializer):
    total = serializers.IntegerField(read_only=True)
    registered = serializers.IntegerField(read_only=True)
    away = serializers.IntegerField(read_only=True)

    class Meta(BoxRefSerializer.Meta):
        fields = BoxRefSerializer.Meta.fields + ("total", "registered", "away")


class SlotSerializer(serializers.ModelSerializer):
    """Requer ``select_related`` de box, personal_dex, specimen e
    form__pokemon__species na queryset."""

    box = BoxRefSerializer(read_only=True)
    form = FormRefSerializer(read_only=True, allow_null=True)
    specimen = SpecimenSummarySerializer(read_only=True, allow_null=True)
    is_shiny_display = serializers.SerializerMethodField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
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


class HuntSerializer(SlotSerializer):
    """Slot da lista de caçadas; requer as anotações de ``filter_hunts``."""

    reasons = serializers.SerializerMethodField()
    shiny_lock = serializers.SerializerMethodField()

    class Meta(SlotSerializer.Meta):
        fields = SlotSerializer.Meta.fields + ("reasons", "shiny_lock")

    @extend_schema_field(
        serializers.ListField(child=serializers.ChoiceField(choices=HUNT_REASONS))
    )
    def get_reasons(self, obj: Slot) -> list[str]:
        return [r for r in HUNT_REASONS if getattr(obj, f"hunt_{r}", False)]

    @extend_schema_field(
        serializers.ChoiceField(
            choices=ShinyLock.LockTypeChoices.values, allow_null=True
        )
    )
    def get_shiny_lock(self, obj: Slot) -> str | None:
        if getattr(obj, "hunt_unobtainable", False):
            return ShinyLock.LockTypeChoices.UNOBTAINABLE
        if getattr(obj, "hunt_distro_only", False):
            return ShinyLock.LockTypeChoices.DISTRO_ONLY
        return None


class PersonalDexSerializer(serializers.ModelSerializer):
    total = serializers.IntegerField(read_only=True)
    registered = serializers.IntegerField(read_only=True)
    away = serializers.IntegerField(read_only=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = PersonalDex
        fields = (
            "id",
            "name",
            "is_shiny_dex",
            "force_new_box",
            "total",
            "registered",
            "away",
        )


class PersonalDexCreateSerializer(serializers.ModelSerializer):
    """Dados para criar um PersonalDex com o conjunto padrão de formas."""

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = PersonalDex
        fields = ("name", "is_shiny_dex", "force_new_box")


class PersonalDexUpdateSerializer(serializers.ModelSerializer):
    """Renomear o dex ou trocar se é shiny dex. ``force_new_box`` não muda:
    o esquema já está instalado nas boxes."""

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = PersonalDex
        fields = ("name", "is_shiny_dex")


class PersonalDexPreviewSerializer(serializers.Serializer):
    """Simulação de um dex padrão: o que seria criado, sem criar nada."""

    forms = serializers.IntegerField()
    boxes_needed = serializers.IntegerField()
    largest_free_run = serializers.IntegerField()
    enough_space = serializers.BooleanField()
    # Boxes novas que a criação faria no fim (0: só usa boxes existentes).
    boxes_to_create = serializers.IntegerField()
    # null sem espaço, ou quando o dex fica todo em boxes novas.
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

        # Slot reservado: o espécime dele está num save e volta para cá.
        current = slot.specimen
        if current and current != specimen and current.location_id:
            raise serializers.ValidationError(
                _(
                    "this slot is reserved for a specimen that is out of HOME; "
                    "bring it back or withdraw it first."
                )
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
    away = serializers.IntegerField()
    first_box = BoxRefSerializer()


class VersionSerializer(serializers.ModelSerializer):
    """Versão de jogo, para o treinador original (``OriginalTrainer.version``).

    Requer ``select_related("version_group")`` na queryset.
    """

    version_group = serializers.CharField(source="version_group.name")
    generation = serializers.CharField(source="version_group.generation")

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Version
        fields = ("name", "version_group", "generation")


class ChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    # O campo some da classe em runtime (vai para ``_declared_fields``); o
    # stub só vê que ele cobre o ``Field.label`` (o rótulo do serializer).
    label = serializers.CharField()  # type: ignore[assignment]


class PokeballChoiceSerializer(ChoiceSerializer):
    sprite_url = serializers.CharField()


class TypeChoiceSerializer(ChoiceSerializer):
    sprite_url = serializers.CharField(allow_null=True)


class SpecimenOptionsSerializer(serializers.Serializer):
    language = ChoiceSerializer(many=True)
    gender = ChoiceSerializer(many=True)
    nature = ChoiceSerializer(many=True)
    pokeball = PokeballChoiceSerializer(many=True)
    type = TypeChoiceSerializer(many=True)
    generation = ChoiceSerializer(many=True)
    origin_mark = ChoiceSerializer(many=True)


class SpecimenChangesSerializer(serializers.ModelSerializer):
    """Campos editáveis em lote; todos opcionais. ``null`` em ``pokeball``,
    ``ot`` e ``captured_at`` remove o valor."""

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Specimen
        fields = (
            "pokeball",
            "ot",
            "language",
            "gender",
            "nature",
            "captured_at",
            "is_shiny",
            "is_alpha",
            "is_from_go",
        )
        extra_kwargs = {field: {"required": False} for field in fields}

    def to_internal_value(self, data):
        # Por padrão o DRF ignora campos desconhecidos; aqui eles são erro,
        # para "apelido em lote" não parecer ter funcionado.
        if isinstance(data, dict):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {
                        field: [_("this field can't be changed in bulk.")]
                        for field in unknown
                    }
                )

        return super().to_internal_value(data)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(_("no changes."))
        if attrs.get("pokeball") == "":
            attrs["pokeball"] = None

        return attrs


class SpecimenIdsSerializer(serializers.Serializer):
    """``ids`` de uma operação em lote, todos existentes (repetidos contam uma
    vez).

    Deve rodar dentro de uma transação: os espécimes ficam travados
    (``select_for_update``) entre a validação e a operação.
    """

    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)

    def validate_ids(self, ids: list[int]) -> list[int]:
        ids = sorted(set(ids))
        # order_by("pk"): trava sempre na mesma ordem e evita os JOINs da
        # ordenação padrão (FOR UPDATE não aceita LEFT JOIN).
        found = set(
            Specimen.objects.select_for_update()
            .filter(pk__in=ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        missing = [pk for pk in ids if pk not in found]
        if missing:
            raise serializers.ValidationError(
                _("specimens not found: %(ids)s")
                % {"ids": ", ".join(map(str, missing))}
            )

        return ids


class SpecimenBulkUpdateSerializer(SpecimenIdsSerializer):
    """``PATCH /specimens/bulk/``: aplica ``changes`` a todos os ``ids``."""

    changes = SpecimenChangesSerializer()

    def gender_conflicts(self) -> list[dict]:
        """Espécimes cuja forma não admite o gênero pedido (vazio se o
        gênero não muda). Fora do ``validate`` porque o ``ValidationError``
        do DRF transformaria os ids em texto."""
        gender = self.validated_data["changes"].get("gender")
        if gender is None:
            return []

        specimens = Specimen.objects.filter(
            pk__in=self.validated_data["ids"]
        ).select_related("form__pokemon__species")
        return [
            {"id": specimen.pk, "form_name": specimen.form.name}
            for specimen in specimens.order_by("pk")
            if gender not in allowed_genders(specimen.form)
        ]

    def save(self, **kwargs) -> int:
        """Número de espécimes atualizados."""
        changes = with_origin_version(self.validated_data["changes"])
        return Specimen.objects.filter(pk__in=self.validated_data["ids"]).update(
            **changes, updated_at=timezone.now()
        )


class SpecimenBulkResultSerializer(serializers.Serializer):
    updated = serializers.IntegerField()


class SpecimenBulkReleaseSerializer(SpecimenIdsSerializer):
    """``POST /specimens/bulk-release/``: liberta (apaga) todos os ``ids``.
    Os slots onde estavam depositados ficam vazios (``on_delete=SET_NULL``),
    como no ``DELETE /specimens/{id}/``."""

    def save(self, **kwargs) -> int:
        """Número de espécimes libertados."""
        ids = self.validated_data["ids"]
        Specimen.objects.filter(pk__in=ids).delete()
        return len(ids)


class SpecimenBulkReleaseResultSerializer(serializers.Serializer):
    released = serializers.IntegerField()


class SpecimenTransferSerializer(SpecimenIdsSerializer):
    """``POST /specimens/transfer/``: leva os ``ids`` para ``save`` (``null``
    = de volta ao HOME). Quem já está lá fica como está (inclusive a data)."""

    def get_fields(self):
        # O campo se chama "save", como o método: declarado aqui para não
        # ser sobrescrito por ele no corpo da classe.
        fields = super().get_fields()
        fields["save"] = serializers.PrimaryKeyRelatedField(
            queryset=Save.objects.all(), allow_null=True
        )
        return fields

    def save(self, **kwargs) -> int:
        """Número de espécimes que mudaram de lugar."""
        destination = self.validated_data["save"]
        return (
            Specimen.objects.filter(pk__in=self.validated_data["ids"])
            .exclude(location=destination)
            .update(
                location=destination,
                location_since=timezone.localdate() if destination else None,
                updated_at=timezone.now(),
            )
        )


class SpecimenTransferResultSerializer(serializers.Serializer):
    transferred = serializers.IntegerField()


def evolves_into(species, target) -> bool:
    """``target`` é uma evolução (direta ou não) de ``species``."""
    current = target.evolves_from_species
    while current is not None:
        if current == species:
            return True
        current = current.evolves_from_species
    return False


class SpecimenEvolveSerializer(serializers.Serializer):
    """``POST /specimens/{id}/evolve/``: o espécime (em ``context``) evoluiu
    fora do HOME e passa a ser ``form``."""

    form = serializers.PrimaryKeyRelatedField(
        queryset=PokemonForm.objects.select_related(
            "pokemon__species__evolves_from_species"
        )
    )

    def validate_form(self, form: PokemonForm) -> PokemonForm:
        specimen: Specimen = self.context["specimen"]
        old = specimen.form.pokemon.species if specimen.form.pokemon else None
        new = form.pokemon.species if form.pokemon else None
        if old is None or new is None or not evolves_into(old, new):
            raise serializers.ValidationError(
                _("this form is not an evolution of the specimen.")
            )
        return form

    def save(self, **kwargs) -> Specimen:
        """Troca a forma, leva a habilidade para o mesmo slot de habilidade
        da forma nova (ou limpa) e tira o espécime do slot, que era da forma
        antiga e volta a faltar."""
        specimen: Specimen = self.context["specimen"]
        form: PokemonForm = self.validated_data["form"]
        specimen.ability = self._evolved_ability(specimen, form)
        specimen.form = form
        specimen.form_name = form.name.strip()
        specimen.save()
        Slot.objects.filter(specimen=specimen).update(specimen=None)
        return specimen

    @staticmethod
    def _evolved_ability(specimen: Specimen, form: PokemonForm) -> str | None:
        old = specimen.form.pokemon.abilities.filter(ability=specimen.ability)
        if specimen.ability is None or not (match := old.first()):
            return None
        new = form.pokemon.abilities.filter(
            slot=match.slot, is_hidden=match.is_hidden
        ).first()
        return new.ability if new else None
