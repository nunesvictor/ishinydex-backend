from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from home.models import Box, OriginalTrainer, PersonalDex, Slot, Specimen
from pokedex.models import PokemonForm

from ..choices import specimen_options
from ..filters import (
    FormSearchFilterBackend,
    SlotFilterBackend,
    SpecimenFilterBackend,
    TrainerSearchFilterBackend,
)
from ..serializers.home import (
    BoxSummarySerializer,
    DepositSerializer,
    FormDetailSerializer,
    FormRefSerializer,
    PersonalDexSerializer,
    SlotSerializer,
    SpecimenOptionsSerializer,
    SpecimenSerializer,
    TrainerSerializer,
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


class PersonalDexViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PersonalDex.objects.annotate(**count_slots("slot__")).order_by("name")
    serializer_class = PersonalDexSerializer

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
        ]
    )
)
class SlotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Slot.objects.select_related(
        "box", "personal_dex", "specimen", "form__pokemon__species"
    )
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


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("form_id", OpenApiTypes.INT),
            OpenApiParameter(
                "available",
                OpenApiTypes.BOOL,
                description=_("true: only specimens not deposited in any slot"),
            ),
            OpenApiParameter("is_shiny", OpenApiTypes.BOOL),
            OpenApiParameter(
                "search", OpenApiTypes.STR, description=_("nickname or form name")
            ),
        ]
    )
)
class SpecimenViewSet(viewsets.ModelViewSet):
    queryset = (
        Specimen.objects.select_related("form__pokemon__species")
        .annotate(
            slot_id=Subquery(
                Slot.objects.filter(specimen=OuterRef("pk")).values("pk")[:1]
            )
        )
        .order_by("form__order", "pk")
    )
    serializer_class = SpecimenSerializer
    filter_backends = (SpecimenFilterBackend,)

    def destroy(self, request, *args, **kwargs):
        specimen = self.get_object()

        if specimen.slot_id is not None:
            return Response(
                {"detail": _("a deposited specimen can't be deleted.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)

    @extend_schema(responses=SpecimenOptionsSerializer)
    @action(detail=False, pagination_class=None, filter_backends=[])
    def options(self, request):
        """Choices de language, gender, nature e pokeball, com labels
        traduzidos."""
        return Response(specimen_options())


@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("search", OpenApiTypes.STR)],
        responses=FormRefSerializer(many=True),
    )
)
class FormViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PokemonForm.objects.select_related("pokemon__species").order_by(
        "order", "pk"
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
