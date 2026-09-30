from django.db import migrations
from django.db.models import OuterRef, Subquery


def fill_origin_version(apps, schema_editor):
    """Jogo de origem dos espécimes existentes = versão do OT (ou vazio)."""
    Specimen = apps.get_model("home", "Specimen")
    OriginalTrainer = apps.get_model("home", "OriginalTrainer")

    Specimen.objects.filter(ot__isnull=False).update(
        origin_version_id=Subquery(
            OriginalTrainer.objects.filter(pk=OuterRef("ot_id")).values(
                "version_id"
            )[:1]
        )
    )


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0003_specimen_origin_version"),
    ]

    operations = [
        migrations.RunPython(fill_origin_version, migrations.RunPython.noop),
    ]
