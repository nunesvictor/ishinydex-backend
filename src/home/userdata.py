"""Dados do usuário no formato do app local (ishinydex#48, etapa 7).

O app sem servidor guarda tudo num arquivo JSON, o mesmo do "Exportar
dados", do "Importar dados" e do sync com o Dropbox::

    {"schemaVersion": 1, "kind": "ishinydex-data", "catalog": "...",
     "savedAt": "...", "records": {"specimens": [{..., "updatedAt": "..."}]},
     "deleted": {}}

Os registros têm os mesmos campos do ``FakeBackend.records`` do frontend:
só ids e valores, nada derivado (sprites, contagens, marca de origem). As
formas vão pelo ``pokeapi_id``, a chave do catálogo do app, e não pelo id
do banco.
"""

from datetime import datetime, timezone

from home.models import Box, OriginalTrainer, PersonalDex, Save, Slot, Specimen
from pokedex.models import ShinyLock

SCHEMA_VERSION = 1
KIND = "ishinydex-data"


def _timestamp(value: datetime) -> str:
    """ISO 8601 em UTC com milissegundos, como o ``toIso8601String`` do Dart
    (o app compara as datas como texto)."""
    utc = value.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


def _date(value) -> str | None:
    return value.isoformat() if value else None


def _record(obj, **fields) -> dict:
    return {"id": obj.pk, **fields, "updatedAt": _timestamp(obj.updated_at)}


def build_user_data(catalog_version: str, now: datetime | None = None) -> dict:
    """O arquivo de dados com tudo do banco."""
    trainers = [
        _record(
            t,
            name=t.name,
            trainerId=t.trainer_id,
            version=t.version.name if t.version else None,
        )
        for t in OriginalTrainer.objects.select_related("version").order_by("pk")
    ]
    saves = [
        _record(s, trainer=s.trainer_id, label=s.label)
        for s in Save.objects.order_by("pk")
    ]
    dexes = [
        _record(
            d,
            name=d.name,
            isShinyDex=d.is_shiny_dex,
            forceNewBox=d.force_new_box,
        )
        for d in PersonalDex.objects.order_by("pk")
    ]
    boxes = [
        _record(b, name=b.name, position=b.position)
        for b in Box.objects.order_by("position")
    ]
    locks = [
        _record(
            lock,
            caption=lock.caption,
            description=lock.description,
            lockType=lock.lock_type,
            active=lock.active,
            forms=sorted(f.pokeapi_id for f in lock.forms.all()),
        )
        for lock in ShinyLock.objects.prefetch_related("forms").order_by("pk")
    ]
    specimens = [
        _record(
            s,
            form=s.form.pokeapi_id,
            nickname=s.nickname,
            ability=s.ability,
            language=s.language,
            gender=s.gender,
            nature=s.nature,
            isAlpha=s.is_alpha,
            isShiny=s.is_shiny,
            isFromGo=s.is_from_go,
            capturedAt=_date(s.captured_at),
            pokeball=s.pokeball,
            observation=s.observation,
            ot=s.ot_id,
            location=s.location_id,
            locationSince=_date(s.location_since),
        )
        for s in Specimen.objects.select_related("form").order_by("pk")
    ]
    slots = [
        _record(
            s,
            box=s.box_id,
            row=s.row,
            col=s.col,
            dex=s.personal_dex_id,
            form=s.form.pokeapi_id if s.form else None,
            specimen=s.specimen_id,
        )
        for s in Slot.objects.select_related("form").order_by(
            "box__position", "position"
        )
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "catalog": catalog_version,
        "savedAt": _timestamp(now or datetime.now(timezone.utc)),
        # Na ordem em que o app restaura (cada tipo só cita os anteriores).
        "records": {
            "trainers": trainers,
            "saves": saves,
            "dexes": dexes,
            "boxes": boxes,
            "shinyLocks": locks,
            "specimens": specimens,
            "slots": slots,
        },
        "deleted": {},
    }
