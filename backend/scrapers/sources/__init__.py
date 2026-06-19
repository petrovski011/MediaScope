"""Registry of all MediaScope scrapers.

SCRAPERS maps source_id -> scraper class.
STAGGERED_ORDER defines the scheduled run sequence (3-minute gaps).
"""
from .b92 import B92Scraper
from .birn import BirnScraper
from .blic import BlicScraper
from .danas import DanasScraper
from .informer import InformerScraper
from .insajder import InsajderScraper
from .juzne import JuzneVestiScraper
from .kurir import KurirScraper
from .mondo import MondoScraper
from .n1 import N1Scraper
from .nova import NovaScraper
from .pink import PinkScraper
from .politika import PolitikaScraper
from .prva import PrvaScraper
from .radar import RadarScraper
from .rts import RtsScraper
from .sd import SrbijaDanasScraper
from .telegraf import TelegrafScraper
from .tanjug import TanjugScraper
from .vreme import VremeScraper

SCRAPERS: dict[str, type] = {
    "n1": N1Scraper,
    "blic": BlicScraper,
    "telegraf": TelegrafScraper,
    "kurir": KurirScraper,
    "sd": SrbijaDanasScraper,
    "rts": RtsScraper,
    "nova": NovaScraper,
    "informer": InformerScraper,
    "danas": DanasScraper,
    "b92": B92Scraper,
    "mondo": MondoScraper,
    "pink": PinkScraper,
    "birn": BirnScraper,
    "radar": RadarScraper,
    "prva": PrvaScraper,
    "juzne": JuzneVestiScraper,
    "vreme": VremeScraper,
    "insajder": InsajderScraper,
    "tanjug": TanjugScraper,
    "politika": PolitikaScraper,
}

# Staggered schedule order — scraper runs every hour, 3-minute gaps between sources
STAGGERED_ORDER = [
    "n1",        # :00
    "blic",      # :03
    "telegraf",  # :06
    "kurir",     # :09
    "sd",        # :12
    "rts",       # :15
    "nova",      # :18
    "informer",  # :21
    "danas",     # :24
    "b92",       # :27
    "mondo",     # :30
    "pink",      # :33
    "birn",      # :36
    "radar",     # :39
    "prva",      # :42
    "juzne",     # :45
    "vreme",     # :48
    "insajder",  # :51
    "tanjug",    # :54
    "politika",  # :57
]

# Sources with confirmed working data collection:
# RSS: n1, telegraf, nova, vreme, insajder, kurir, sd, danas, birn, radar
# HTML listing: rts, informer, b92, tanjug, prva, blic, pink, politika
# Stubs (Playwright/bypass needed): mondo, juzne

__all__ = ["SCRAPERS", "STAGGERED_ORDER"] + [cls.__name__ for cls in SCRAPERS.values()]
