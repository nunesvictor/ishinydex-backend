from django.db import transaction
from django.db.models import Count, F, Min, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from drf_spectacular.plumbing import build_array_type, build_basic_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from home.models import Box, OriginalTrainer, PersonalDex, Slot, Specimen
from home.services import (
    HOME_MAX_BOXES,
    NotEnoughBoxes,
    create_default_dex,
    delete_dex,
    plan_default_dex,
)
from pokedex.models import PokemonForm, Version

from ..choices import specimen_options
from ..filters import (
    SPECIMEN_ORDERINGS,
    FormSearchFilterBackend,
    SlotFilterBackend,
    SpecimenFilterBackend,
    TrainerSearchFilterBackend,
    filter_hunts,
    parse_bool,
)
from ..serializers.home import (
    BoxSummarySerializer,
    DepositSerializer,
    FormDetailSerializer,
    FormRefSerializer,
    GenerationProgressSerializer,
    HuntSerializer,
    PersonalDexCreateSerializer,
    PersonalDexPreviewSerializer,
    PersonalDexSerializer,
    PersonalDexUpdateSerializer,
    SlotSerializer,
    SpecimenBulkResultSerializer,
    SpecimenBulkUpdateSerializer,
    SpecimenOptionsSerializer,
    SpecimenSerializer,
    TrainerSerializer,
    VersionSerializer,
    national_number_prefetch,
    pokeball_sprite_url,
    type_sprite_url,
)


def count_slots(prefix: str, **filters) -> dict:
    """Anotações ``total`` (slots com forma) e ``registered`` (com specimen)."""
    base = Q(**{f"{prefix}form__isnull": False}) & Q(
        **{f"{prefix}{k}": v for k, v in filters.items()}
    )
    return {
        "total": Count(prefix.rstrip("_"), filter=base),
        "registered": Count(
            prefix.rstrip("_"),
            filter=base & Q(**{f"{prefix}specimen__isnull": False}),
        ),
    }


def not_enough_boxes_message(plan) -> str:
    return _(
        "There aren't enough free boxes in a row for this PersonalDex: it needs "
        "%(needed)d, the largest free sequence has %(largest)d, and creating the "
        "missing boxes would go past the %(max)d boxes of Pokémon HOME."
    ) % {
        "needed": plan.boxes_needed,
        "largest": plan.largest_free_run,
        "max": HOME_MAX_BOXES,
    }


class PersonalDexViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = PersonalDex.objects.annotate(**count_slots("slot__")).order_by("name")
    serializer_class = PersonalDexSerializer
    # Sem PUT: só PATCH (nome e is_shiny_dex).
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    @extend_schema(
        request=PersonalDexCreateSerializer, responses={201: PersonalDexSerializer}
    )
    def create(self, request, *args, **kwargs):
        """Cria o dex com o conjunto padrão de formas e instala o esquema na
        primeira sequência de boxes livres que comporte todas elas, criando
        no fim as boxes que faltarem (até o limite do HOME)."""
        serializer = PersonalDexCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            dex = create_default_dex(**serializer.validated_data)
        except NotEnoughBoxes as error:
            return Response(
                {"non_field_errors": [not_enough_boxes_message(error.plan)]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = PersonalDexSerializer(self.get_queryset().get(pk=dex.pk)).data
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(request=PersonalDexUpdateSerializer, responses=PersonalDexSerializer)
    def partial_update(self, request, *args, **kwargs):
        """Renomeia o dex ou troca se é shiny dex."""
        dex = self.get_object()
        serializer = PersonalDexUpdateSerializer(dex, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PersonalDexSerializer(self.get_queryset().get(pk=dex.pk)).data)

    def perform_destroy(self, instance):
        """Apaga o dex e libera os slots; os espécimes depositados voltam a
        ficar disponíveis no inventário."""
        delete_dex(instance)

    @extend_schema(
        parameters=[OpenApiParameter("force_new_box", OpenApiTypes.BOOL)],
        responses=PersonalDexPreviewSerializer,
    )
    @action(detail=False, pagination_class=None)
    def preview(self, request):
        """Simula um dex padrão (quantas formas, quantas boxes e onde começa),
        sem criar nada."""
        plan = plan_default_dex(
            parse_bool(request.query_params.get("force_new_box")) or False
        )
        data = {
            "forms": len(plan.forms),
            "boxes_needed": plan.boxes_needed,
            "largest_free_run": plan.largest_free_run,
            "enough_space": plan.enough_space,
            "boxes_to_create": plan.boxes_to_create,
            "first_box": plan.boxes[0] if plan.boxes else None,
        }
        return Response(PersonalDexPreviewSerializer(data).data)

    @extend_schema(responses=BoxSummarySerializer(many=True))
    @action(detail=True, pagination_class=None)
    def boxes(self, request, pk=None):
        """Boxes que têm slots do dex, com as contagens daquele dex."""
        dex = get_object_or_404(PersonalDex, pk=pk)
        boxes = (
            Box.objects.annotate(
                dex_slots=Count("slots", filter=Q(slots__personal_dex=dex)),
                **count_slots("slots__", personal_dex=dex),
            )
            .filter(dex_slots__gt=0)
            .order_by("position")
        )
        serializer = BoxSummarySerializer(
            boxes, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @extend_schema(responses=GenerationProgressSerializer(many=True))
    @action(detail=True, pagination_class=None)
    def generations(self, request, pk=None):
        """Total e registrados por geração, na ordem em que as gerações
        aparecem nas boxes, com a box onde cada uma começa."""
        dex = get_object_or_404(PersonalDex, pk=pk)
        rows = list(
            Slot.objects.filter(personal_dex=dex, form__isnull=False)
            .values(generation=F("form__pokemon__species__generation"))
            .annotate(
                total=Count("id"),
                registered=Count("id", filter=Q(specimen__isnull=False)),
                first_box_position=Min("box__position"),
            )
            .order_by("first_box_position", "generation")
        )
        # `position` é sequencial (OrderedModel), mas não tem unique no banco:
        # sem in_bulk(field_name=...).
        boxes = {
            box.position: box
            for box in Box.objects.filter(
                position__in=[row["first_box_position"] for row in rows]
            )
        }
        data = [
            {
                "generation": row["generation"],
                "total": row["total"],
                "registered": row["registered"],
                "first_box": boxes[row["first_box_position"]],
            }
            for row in rows
        ]
        return Response(GenerationProgressSerializer(data, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "reasons",
                OpenApiTypes.STR,
                description=_(
                    "comma-separated reasons (any of them): no_shiny, from_go, "
                    "pokeball; default: no_shiny"
                ),
            ),
            OpenApiParameter(
                "accepted_balls",
                OpenApiTypes.STR,
                description=_(
                    "comma-separated pokéballs for the pokeball reason; "
                    "specimens without pokéball are not listed by it"
                ),
            ),
            OpenApiParameter(
                "generation", OpenApiTypes.STR, description=_("comma-separated")
            ),
            OpenApiParameter(
                "type",
                OpenApiTypes.STR,
                description=_("comma-separated types; the form must have any"),
            ),
            OpenApiParameter(
                "category",
                OpenApiTypes.STR,
                description=_(
                    "comma-separated (any of them): legendary, mythical, "
                    "ultra-beast, baby, regular"
                ),
            ),
            OpenApiParameter(
                "search",
                OpenApiTypes.STR,
                description=_(
                    "form name, national dex number or the form's PokéAPI ID"
                ),
            ),
            OpenApiParameter(
                "include_locked",
                OpenApiTypes.BOOL,
                description=_("include forms whose shiny is unobtainable"),
            ),
        ],
        responses=HuntSerializer(many=True),
    )
    @action(detail=True)
    def hunts(self, request, pk=None):
        """Slots de um shiny dex que ainda precisam ser caçados, na ordem das
        boxes, com os motivos de cada um."""
        dex = get_object_or_404(PersonalDex, pk=pk)
        if not dex.is_shiny_dex:
            return Response(
                {"detail": _("Hunts are only available for shiny dexes.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slots = filter_hunts(
            Slot.objects.filter(personal_dex=dex)
            .select_related("box", "personal_dex", "specimen", "form__pokemon__species")
            .prefetch_related(national_number_prefetch("form__")),
            request.query_params,
        )
        page = self.paginate_queryset(slots)
        serializer = HuntSerializer(
            page, many=True, context=self.get_serializer_context()
        )
        return self.get_paginated_response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("personal_dex", OpenApiTypes.INT),
            OpenApiParameter(
                "box",
                OpenApiTypes.INT,
                description=_("when set, returns all box slots, without pagination"),
            ),
            OpenApiParameter("registered", OpenApiTypes.BOOL),
            OpenApiParameter(
                "search",
                OpenApiTypes.STR,
                description=_(
                    "form name, national dex number or the form's PokéAPI ID"
                ),
            ),
        ]
    )
)
class SlotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Slot.objects.select_related(
        "box", "personal_dex", "specimen", "form__pokemon__species"
    ).prefetch_related(national_number_prefetch("form__"))
    serializer_class = SlotSerializer
    filter_backends = (SlotFilterBackend,)

    def paginate_queryset(self, queryset):
        # Uma box inteira (30 slots) é sempre retornada de uma vez.
        if self.request.query_params.get("box"):
            return None

        return super().paginate_queryset(queryset)

    def _slot_response(self, pk):
        slot = self.get_queryset().get(pk=pk)
        return Response(self.get_serializer(slot).data)

    @extend_schema(request=DepositSerializer, responses=SlotSerializer)
    @action(detail=True, methods=["post"])
    def deposit(self, request, pk=None):
        with transaction.atomic():
            slot = get_object_or_404(Slot.objects.select_for_update(), pk=pk)
            serializer = DepositSerializer(
                data=request.data, context={"request": request, "slot": slot}
            )
            serializer.is_valid(raise_exception=True)
            slot.specimen = serializer.validated_data["specimen_id"]
            slot.save(update_fields=["specimen", "updated_at"])

        return self._slot_response(slot.pk)

    @extend_schema(request=None, responses=SlotSerializer)
    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        with transaction.atomic():
            slot = get_object_or_404(Slot.objects.select_for_update(), pk=pk)
            slot.specimen = None
            slot.save(update_fields=["specimen", "updated_at"])

        return self._slot_response(slot.pk)


# Filtros de GET /specimens/ (e de /specimens/ids/), para o schema.
SPECIMEN_FILTER_PARAMETERS = [
    OpenApiParameter("form_id", OpenApiTypes.INT),
    OpenApiParameter(
        "id", OpenApiTypes.STR, description=_("comma-separated specimen ids")
    ),
    OpenApiParameter(
        "available",
        OpenApiTypes.BOOL,
        description=_("true: only specimens not deposited in any slot"),
    ),
    OpenApiParameter("is_shiny", OpenApiTypes.BOOL),
    OpenApiParameter("is_alpha", OpenApiTypes.BOOL),
    OpenApiParameter("is_from_go", OpenApiTypes.BOOL),
    OpenApiParameter(
        "search",
        OpenApiTypes.STR,
        description=_(
            "nickname or form name; a number: national dex number or the form's "
            "PokéAPI ID"
        ),
    ),
    OpenApiParameter(
        "pokeball",
        OpenApiTypes.STR,
        description=_("comma-separated pokéballs; none: without pokéball"),
    ),
    OpenApiParameter(
        "type",
        OpenApiTypes.STR,
        description=_("comma-separated types; the form must have all"),
    ),
    OpenApiParameter(
        "ot",
        OpenApiTypes.STR,
        description=_("comma-separated trainer ids; none: without OT"),
    ),
    OpenApiParameter(
        "generation",
        OpenApiTypes.STR,
        description=_("comma-separated generations (generation-i...)"),
    ),
    OpenApiParameter(
        "origin_mark",
        OpenApiTypes.STR,
        description=_(
            "comma-separated origin marks (paldea, galar, go...); none: without mark"
        ),
    ),
    OpenApiParameter("gender", OpenApiTypes.STR, description=_("comma-separated")),
    OpenApiParameter("nature", OpenApiTypes.STR, description=_("comma-separated")),
    OpenApiParameter("language", OpenApiTypes.STR, description=_("comma-separated")),
    OpenApiParameter("ability", OpenApiTypes.STR),
    OpenApiParameter("captured_after", OpenApiTypes.DATE),
    OpenApiParameter("captured_before", OpenApiTypes.DATE),
    OpenApiParameter(
        "ordering",
        OpenApiTypes.STR,
        enum=list(SPECIMEN_ORDERINGS),
        description=_("default: dex"),
    ),
]


@extend_schema_view(list=extend_schema(parameters=SPECIMEN_FILTER_PARAMETERS))
class SpecimenViewSet(viewsets.ModelViewSet):
    queryset = (
        Specimen.objects.select_related(
            "form__pokemon__species", "origin_version__version_group"
        )
        .prefetch_related(national_number_prefetch("form__"))
        .annotate(
            slot_id=Subquery(
                Slot.objects.filter(specimen=OuterRef("pk")).values("pk")[:1]
            )
        )
        .order_by("form__order", "pk")
    )
    serializer_class = SpecimenSerializer
    filter_backends = (SpecimenFilterBackend,)

    @extend_schema(responses=SpecimenOptionsSerializer)
    @action(detail=False, pagination_class=None, filter_backends=[])
    def options(self, request):
        """Choices de language, gender, nature, pokeball, type, generation e
        origin_mark,
        com labels traduzidos. Pokébolas e tipos trazem também a URL absoluta
        do sprite (``null`` se o tipo não tiver ícone)."""
        options = specimen_options()

        for ball in options["pokeball"]:
            ball["sprite_url"] = pokeball_sprite_url(request, ball["value"])

        for type_ in options["type"]:
            type_["sprite_url"] = type_sprite_url(request, type_["value"])

        return Response(options)

    @extend_schema(
        parameters=SPECIMEN_FILTER_PARAMETERS,
        responses={200: build_array_type(build_basic_type(OpenApiTypes.INT))},
    )
    @action(detail=False, pagination_class=None)
    def ids(self, request):
        """Ids de todos os espécimes do filtro, na mesma ordem da lista e sem
        paginação: o app seleciona "todos os resultados" para editar em
        lote."""
        queryset = self.filter_queryset(self.get_queryset())
        return Response(list(queryset.values_list("pk", flat=True)))

    @extend_schema(
        request=SpecimenBulkUpdateSerializer,
        responses=SpecimenBulkResultSerializer,
    )
    @action(detail=False, methods=["patch"], filter_backends=[])
    @transaction.atomic
    def bulk(self, request):
        """Edição em lote: aplica ``changes`` a todos os ``ids``, tudo ou
        nada. Gênero incompatível com a forma de algum espécime → 400 com a
        lista ``conflicts``."""
        serializer = SpecimenBulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if conflicts := serializer.gender_conflicts():
            message = _("this gender is not possible for %(count)d specimen(s).")
            return Response(
                {
                    "gender": [message % {"count": len(conflicts)}],
                    "conflicts": conflicts,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"updated": serializer.save()})


@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("search", OpenApiTypes.STR)],
        responses=FormRefSerializer(many=True),
    )
)
class FormViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        PokemonForm.objects.select_related("pokemon__species")
        .prefetch_related(national_number_prefetch())
        .order_by("order", "pk")
    )
    filter_backends = (FormSearchFilterBackend,)

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == "retrieve":
            queryset = queryset.prefetch_related("types", "pokemon__abilities")

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return FormDetailSerializer

        return FormRefSerializer


@extend_schema_view(
    list=extend_schema(parameters=[OpenApiParameter("search", OpenApiTypes.STR)])
)
class TrainerViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = OriginalTrainer.objects.select_related("version")
    serializer_class = TrainerSerializer
    filter_backends = (TrainerSearchFilterBackend,)


class VersionViewSet(viewsets.ReadOnlyModelViewSet):
    """Versões de jogo em ordem de lançamento (poucas dezenas: sem
    paginação), para escolher a versão do treinador original."""

    queryset = Version.objects.select_related("version_group").order_by(
        "version_group__order", "pk"
    )
    serializer_class = VersionSerializer
    pagination_class = None
    lookup_field = "name"
