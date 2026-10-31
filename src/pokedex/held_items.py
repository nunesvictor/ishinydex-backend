"""Importação dos itens seguráveis por grupo de versões (#138).

A lista de cada jogo vem do Showdown (``pokedex.showdown``), pelo mod que
``HELD_ITEMS_FILE`` dá a cada grupo de versões; da PokéAPI vem só o nome do
item (o slug, que dá o sprite). Falha, em vez de passar calada, com grupo de
versões sem mod no arquivo (jogo novo), com mod desconhecido e com item do
Showdown sem par na PokéAPI que não esteja em ``withoutSprite``.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path

from django.db import transaction

from core.services.pokeapi import PokeAPIClient
from pokedex.models import HeldItem, VersionGroup
from pokedex.showdown import ShowdownError, ShowdownItems

HELD_ITEMS_FILE = Path(__file__).resolve().parent / "data/held_items.json"


class HeldItemsError(ValueError):
    pass


def item_slug(name: str) -> str:
    """O slug da PokéAPI para o nome do Showdown: ``"King's Rock"`` →
    ``"kings-rock"``, ``"Flabébé"`` → ``"flabebe"``."""
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-").replace("é", "e"))


class HeldItemsImporter:
    def __init__(
        self,
        client: PokeAPIClient,
        showdown: ShowdownItems,
        log: Callable[[str], None] = print,
    ):
        self.client = client
        self.showdown = showdown
        self.log = log

    @transaction.atomic
    def run(self) -> int:
        data = json.loads(HELD_ITEMS_FILE.read_text(encoding="utf-8"))
        mods: dict[str, str | None] = data["versionGroups"]
        groups = dict(VersionGroup.objects.values_list("name", "id"))
        if missing := sorted(groups.keys() - mods.keys()):
            raise HeldItemsError(f"grupos de versões sem mod do Showdown: {missing}")

        pokeapi = {r["name"] for r in self.client.list("item")}
        aliases: dict[str, str] = data["aliases"]
        without_sprite = set(data["withoutSprite"])

        def resolve(label: str) -> tuple[str, bool]:
            slug = aliases.get(label, item_slug(label))
            # Os Z-Crystals têm duas versões na PokéAPI; a segurável é a "--held".
            for name in (slug, f"{slug}--held"):
                if name in pokeapi:
                    return name, True
            if label in without_sprite:
                return slug, False
            raise HeldItemsError(f"item do Showdown sem par na PokéAPI: {label}")

        items: dict[str, tuple[str, bool]] = {}
        pairs: list[tuple[str, int]] = []
        for group, mod in mods.items():
            if mod is None or group not in groups:
                continue
            try:
                labels = self.showdown.held_items(mod).values()
            except ShowdownError as error:
                raise HeldItemsError(str(error)) from None
            for label in labels:
                name, has_sprite = resolve(label)
                items[name] = (label, has_sprite)
                pairs.append((name, groups[group]))

        HeldItem.objects.bulk_create(
            [
                HeldItem(name=name, label=label, has_sprite=has_sprite)
                for name, (label, has_sprite) in items.items()
            ],
            update_conflicts=True,
            unique_fields=["name"],
            update_fields=["label", "has_sprite", "updated_at"],
        )
        HeldItem.objects.exclude(name__in=items).delete()
        ids = dict(HeldItem.objects.values_list("name", "id"))
        through = HeldItem.version_groups.through
        through.objects.all().delete()
        through.objects.bulk_create(
            [
                through(helditem_id=ids[name], versiongroup_id=group)
                for name, group in dict.fromkeys(pairs)
            ],
            batch_size=2000,
        )
        self.log(f"  {HeldItem._meta.verbose_name_plural}: {len(items)}")
        return len(items)
