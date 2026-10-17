from django.test import TestCase

from core.tests import factories as f
from home.models import PersonalDex, Slot
from home.services import default_forms, delete_dex


class DeleteDexTests(TestCase):
    def test_frees_slots_and_keeps_specimens(self):
        form = f.make_full_pokemon("bulbasaur", 1)[2]
        box = f.make_box(name="HOME 1")
        dex = f.make_personal_dex(form, name="Living")
        specimen = f.make_specimen(form)
        Slot.objects.filter(box=box, row=0, col=0).update(
            form=form, personal_dex=dex, specimen=specimen
        )

        delete_dex(dex)

        self.assertFalse(PersonalDex.objects.exists())
        # A box ficou livre: nenhum slot com forma ou dex.
        self.assertFalse(
            Slot.objects.filter(box=box).exclude(form=None, personal_dex=None).exists()
        )
        specimen.refresh_from_db()
        self.assertFalse(Slot.objects.filter(specimen=specimen).exists())


class DefaultFormsTests(TestCase):
    def test_minior_keeps_the_cores_without_the_meteor_shells(self):
        _, pokemon, _ = f.make_full_pokemon("minior", 774)
        pokemon.forms.all().delete()
        for color in ("red", "orange", "violet"):
            f.make_form(pokemon, name=f"minior-{color}-meteor")
            f.make_form(pokemon, name=f"minior-{color}")

        names = set(default_forms().values_list("name", flat=True))

        self.assertEqual(names, {"minior-red", "minior-orange", "minior-violet"})

    def test_every_alcremie_but_the_battle_form(self):
        _, pokemon, _ = f.make_full_pokemon("alcremie", 869)
        pokemon.forms.all().delete()
        for cream in ("vanilla-cream", "ruby-cream", "rainbow-swirl"):
            f.make_form(pokemon, name=f"alcremie-{cream}-strawberry-sweet")
        f.make_form(pokemon, name="alcremie-gmax", is_battle_only=True)

        names = set(default_forms().values_list("name", flat=True))

        self.assertEqual(
            names,
            {
                "alcremie-vanilla-cream-strawberry-sweet",
                "alcremie-ruby-cream-strawberry-sweet",
                "alcremie-rainbow-swirl-strawberry-sweet",
            },
        )
