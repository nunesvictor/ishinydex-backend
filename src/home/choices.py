from django.db import models
from django.utils.translation import gettext_lazy as _


class Pokeball(models.TextChoices):
    # Standard & Special Balls
    POKE_BALL = "poke-ball", _("Poké Ball")
    GREAT_BALL = "great-ball", _("Great Ball")
    ULTRA_BALL = "ultra-ball", _("Ultra Ball")
    MASTER_BALL = "master-ball", _("Master Ball")
    PREMIER_BALL = "premier-ball", _("Premier Ball")
    HEAL_BALL = "heal-ball", _("Heal Ball")
    NET_BALL = "net-ball", _("Net Ball")
    NEST_BALL = "nest-ball", _("Nest Ball")
    DIVE_BALL = "dive-ball", _("Dive Ball")
    DUSK_BALL = "dusk-ball", _("Dusk Ball")
    TIMER_BALL = "timer-ball", _("Timer Ball")
    QUICK_BALL = "quick-ball", _("Quick Ball")
    REPEAT_BALL = "repeat-ball", _("Repeat Ball")
    LUXURY_BALL = "luxury-ball", _("Luxury Ball")

    # Apricorn & Rare Balls
    FAST_BALL = "fast-ball", _("Fast Ball")
    FRIEND_BALL = "friend-ball", _("Friend Ball")
    LURE_BALL = "lure-ball", _("Lure Ball")
    LEVEL_BALL = "level-ball", _("Level Ball")
    HEAVY_BALL = "heavy-ball", _("Heavy Ball")
    LOVE_BALL = "love-ball", _("Love Ball")
    MOON_BALL = "moon-ball", _("Moon Ball")
    DREAM_BALL = "dream-ball", _("Dream Ball")
    SPORT_BALL = "sport-ball", _("Sport Ball")
    SAFARI_BALL = "safari-ball", _("Safari Ball")
    BEAST_BALL = "beast-ball", _("Beast Ball")
    CHERISH_BALL = "cherish-ball", _("Cherish Ball")

    # Pokémon Legends: Arceus Balls (Hisui)
    LA_POKE_BALL = "lapoke-ball", _("Poké Ball")
    LA_GREAT_BALL = "lagreat-ball", _("Great Ball")
    LA_ULTRA_BALL = "laultra-ball", _("Ultra Ball")
    LA_FEATHER_BALL = "lafeather-ball", _("Feather Ball")
    LA_WING_BALL = "lawing-ball", _("Wing Ball")
    LA_JET_BALL = "lajet-ball", _("Jet Ball")
    LA_HEAVY_BALL = "laheavy-ball", _("Heavy Ball")
    LA_LEADEN_BALL = "laleaden-ball", _("Leaden Ball")
    LA_GIGATON_BALL = "lagigaton-ball", _("Gigaton Ball")
    LA_ORIGIN_BALL = "laorigin-ball", _("Origin Ball")
