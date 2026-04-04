from __future__ import annotations

import ipaddress
import logging
import pickle
import re
import secrets
from collections.abc import AsyncGenerator
from collections.abc import Mapping
from collections.abc import MutableMapping
from pathlib import Path
from typing import TypedDict

import datadog as datadog_module
import datadog.threadstats.base as datadog_client
import httpx
import pymysql
from redis import asyncio as aioredis

import app.settings
import app.state
from app._typing import IPAddress
from app.adapters.database import Database
from app.logging import Ansi
from app.logging import log

STRANGE_LOG_DIR = Path.cwd() / ".data/logs/strange_occurrences/"

VERSION_RGX = re.compile(r"^# v(?P<ver>\d+\.\d+\.\d+)$")
SQL_UPDATES_FILE = Path.cwd() / "migrations/migrations.sql"


""" session objects """

http_client = httpx.AsyncClient()
database = Database(app.settings.DB_DSN)
redis: aioredis.Redis = aioredis.from_url(app.settings.REDIS_DSN)  # type: ignore[no-untyped-call]

datadog: datadog_client.ThreadStats | None = None
if str(app.settings.DATADOG_API_KEY) and str(app.settings.DATADOG_APP_KEY):
    datadog_module.initialize(
        api_key=str(app.settings.DATADOG_API_KEY),
        app_key=str(app.settings.DATADOG_APP_KEY),
    )
    datadog = datadog_client.ThreadStats()  # type: ignore[no-untyped-call]

ip_resolver: IPResolver

""" session usecases """


class Country(TypedDict):
    acronym: str
    numeric: int


class Geolocation(TypedDict):
    latitude: float
    longitude: float
    country: Country


# fmt: off
country_codes = {
    "ad": 20,  # Andorra
    "ae": 784,  # United Arab Emirates
    "af": 4,  # Afghanistan
    "ag": 28,  # Antigua and Barbuda
    "ai": 660,  # Anguilla
    "al": 8,  # Albania
    "am": 51,  # Armenia
    "ao": 24,  # Angola
    "aq": 10,  # Antarctica
    "ar": 32,  # Argentina
    "as": 16,  # American Samoa
    "at": 40,  # Austria
    "au": 36,  # Australia
    "aw": 533,  # Aruba
    "ax": 248,  # Åland Islands
    "az": 31,  # Azerbaijan
    "ba": 70,  # Bosnia and Herzegovina
    "bb": 52,  # Barbados
    "bd": 50,  # Bangladesh
    "be": 56,  # Belgium
    "bf": 854,  # Burkina Faso
    "bg": 100,  # Bulgaria
    "bh": 48,  # Bahrain
    "bi": 108,  # Burundi
    "bj": 204,  # Benin
    "bl": 652,  # Saint Barthélemy
    "bm": 60,  # Bermuda
    "bn": 96,  # Brunei Darussalam
    "bo": 68,  # Bolivia (Plurinational State of)
    "br": 76,  # Brazil
    "bs": 44,  # Bahamas
    "bt": 64,  # Bhutan
    "bv": 74,  # Bouvet Island
    "bw": 72,  # Botswana
    "by": 112,  # Belarus
    "bz": 84,  # Belize
    "ca": 124,  # Canada
    "cc": 166,  # Cocos (Keeling) Islands
    "cd": 180,  # Congo, Democratic Republic of the
    "cf": 140,  # Central African Republic
    "cg": 178,  # Congo
    "ch": 756,  # Switzerland
    "ci": 384,  # Côte d'Ivoire
    "ck": 184,  # Cook Islands
    "cl": 152,  # Chile
    "cm": 120,  # Cameroon
    "cn": 156,  # China
    "co": 170,  # Colombia
    "cr": 188,  # Costa Rica
    "cu": 192,  # Cuba
    "cv": 132,  # Cabo Verde
    "cw": 531,  # Curaçao
    "cx": 162,  # Christmas Island
    "cy": 196,  # Cyprus
    "cz": 203,  # Czechia
    "de": 276,  # Germany
    "dj": 262,  # Djibouti
    "dk": 208,  # Denmark
    "dm": 212,  # Dominica
    "do": 214,  # Dominican Republic
    "dz": 12,  # Algeria
    "ec": 218,  # Ecuador
    "ee": 233,  # Estonia
    "eg": 818,  # Egypt
    "eh": 732,  # Western Sahara
    "er": 232,  # Eritrea
    "es": 724,  # Spain
    "et": 231,  # Ethiopia
    "fi": 246,  # Finland
    "fj": 242,  # Fiji
    "fk": 238,  # Falkland Islands (Malvinas)
    "fm": 583,  # Micronesia (Federated States of)
    "fo": 234,  # Faroe Islands
    "fr": 250,  # France
    "ga": 266,  # Gabon
    "gb": 826,  # United Kingdom of Great Britain and Northern Ireland
    "gd": 308,  # Grenada
    "ge": 268,  # Georgia
    "gf": 254,  # French Guiana
    "gg": 831,  # Guernsey
    "gh": 288,  # Ghana
    "gi": 292,  # Gibraltar
    "gl": 304,  # Greenland
    "gm": 270,  # Gambia
    "gn": 324,  # Guinea
    "gp": 312,  # Guadeloupe
    "gq": 226,  # Equatorial Guinea
    "gr": 300,  # Greece
    "gs": 239,  # South Georgia and the South Sandwich Islands
    "gt": 320,  # Guatemala
    "gu": 316,  # Guam
    "gw": 624,  # Guinea-Bissau
    "gy": 328,  # Guyana
    "hk": 344,  # Hong Kong
    "hm": 334,  # Heard Island and McDonald Islands
    "hn": 340,  # Honduras
    "hr": 191,  # Croatia
    "ht": 332,  # Haiti
    "hu": 348,  # Hungary
    "id": 360,  # Indonesia
    "ie": 372,  # Ireland
    "il": 376,  # Israel
    "im": 833,  # Isle of Man
    "in": 356,  # India
    "iq": 368,  # Iraq
    "ir": 364,  # Iran (Islamic Republic of)
    "is": 352,  # Iceland
    "it": 380,  # Italy
    "je": 832,  # Jersey
    "jm": 388,  # Jamaica
    "jo": 400,  # Jordan
    "jp": 392,  # Japan
    "ke": 404,  # Kenya
    "kg": 417,  # Kyrgyzstan
    "kh": 116,  # Cambodia
    "ki": 296,  # Kiribati
    "km": 174,  # Comoros
    "kn": 659,  # Saint Kitts and Nevis
    "kp": 408,  # Korea (Democratic People's Republic of)
    "kr": 410,  # Korea, Republic of
    "kw": 414,  # Kuwait
    "ky": 136,  # Cayman Islands
    "kz": 398,  # Kazakhstan
    "la": 418,  # Lao People's Democratic Republic
    "lb": 422,  # Lebanon
    "lc": 662,  # Saint Lucia
    "li": 438,  # Liechtenstein
    "lk": 144,  # Sri Lanka
    "lr": 430,  # Liberia
    "ls": 426,  # Lesotho
    "lt": 440,  # Lithuania
    "lu": 442,  # Luxembourg
    "lv": 428,  # Latvia
    "ly": 434,  # Libya
    "ma": 504,  # Morocco
    "mc": 492,  # Monaco
    "md": 498,  # Moldova, Republic of
    "me": 499,  # Montenegro
    "mf": 663,  # Saint Martin (French part)
    "mg": 450,  # Madagascar
    "mh": 584,  # Marshall Islands
    "mk": 807,  # North Macedonia
    "ml": 466,  # Mali
    "mm": 104,  # Myanmar
    "mn": 496,  # Mongolia
    "mo": 446,  # Macao
    "mp": 580,  # Northern Mariana Islands
    "mq": 474,  # Martinique
    "mr": 478,  # Mauritania
    "ms": 500,  # Montserrat
    "mt": 470,  # Malta
    "mu": 480,  # Mauritius
    "mv": 462,  # Maldives
    "mw": 454,  # Malawi
    "mx": 484,  # Mexico
    "my": 458,  # Malaysia
    "mz": 508,  # Mozambique
    "na": 516,  # Namibia
    "nc": 540,  # New Caledonia
    "ne": 562,  # Niger
    "nf": 574,  # Norfolk Island
    "ng": 566,  # Nigeria
    "ni": 558,  # Nicaragua
    "nl": 528,  # Netherlands
    "no": 578,  # Norway
    "np": 524,  # Nepal
    "nr": 520,  # Nauru
    "nu": 570,  # Niue
    "nz": 554,  # New Zealand
    "om": 512,  # Oman
    "pa": 591,  # Panama
    "pe": 604,  # Peru
    "pf": 258,  # French Polynesia
    "pg": 598,  # Papua New Guinea
    "ph": 608,  # Philippines
    "pk": 586,  # Pakistan
    "pl": 616,  # Poland
    "pm": 666,  # Saint Pierre and Miquelon
    "pn": 612,  # Pitcairn
    "pr": 630,  # Puerto Rico
    "ps": 275,  # Palestine, State of
    "pt": 620,  # Portugal
    "pw": 585,  # Palau
    "py": 600,  # Paraguay
    "qa": 634,  # Qatar
    "re": 638,  # Réunion
    "ro": 642,  # Romania
    "rs": 688,  # Serbia
    "ru": 643,  # Russian Federation
    "rw": 646,  # Rwanda
    "sa": 682,  # Saudi Arabia
    "sb": 90,  # Solomon Islands
    "sc": 690,  # Seychelles
    "sd": 729,  # Sudan
    "se": 752,  # Sweden
    "sg": 702,  # Singapore
    "sh": 654,  # Saint Helena, Ascension and Tristan da Cunha
    "si": 705,  # Slovenia
    "sj": 744,  # Svalbard and Jan Mayen
    "sk": 703,  # Slovakia
    "sl": 694,  # Sierra Leone
    "sm": 674,  # San Marino
    "sn": 686,  # Senegal
    "so": 706,  # Somalia
    "sr": 740,  # Suriname
    "st": 678,  # Sao Tome and Principe
    "sv": 222,  # El Salvador
    "sy": 760,  # Syrian Arab Republic
    "sz": 748,  # Eswatini
    "tc": 796,  # Turks and Caicos Islands
    "td": 148,  # Chad
    "tf": 260,  # French Southern Territories
    "tg": 768,  # Togo
    "th": 764,  # Thailand
    "tj": 762,  # Tajikistan
    "tk": 772,  # Tokelau
    "tl": 626,  # Timor-Leste
    "tm": 795,  # Turkmenistan
    "tn": 788,  # Tunisia
    "to": 776,  # Tonga
    "tr": 792,  # Türkiye
    "tt": 780,  # Trinidad and Tobago
    "tv": 798,  # Tuvalu
    "tw": 158,  # Taiwan, Province of China
    "tz": 834,  # Tanzania, United Republic of
    "ua": 804,  # Ukraine
    "ug": 800,  # Uganda
    "us": 840,  # United States of America
    "uy": 858,  # Uruguay
    "uz": 860,  # Uzbekistan
    "va": 336,  # Holy See
    "vc": 670,  # Saint Vincent and the Grenadines
    "ve": 862,  # Venezuela (Bolivarian Republic of)
    "vg": 92,  # Virgin Islands (British)
    "vi": 850,  # Virgin Islands (U.S.)
    "vn": 704,  # Viet Nam
    "vu": 548,  # Vanuatu
    "wf": 876,  # Wallis and Futuna
    "ws": 882,  # Samoa
    "ye": 887,  # Yemen
    "yt": 175,  # Mayotte
    "za": 710,  # South Africa
    "zm": 894,  # Zambia
    "zw": 716,  # Zimbabwe
}

# fmt: on


class IPResolver:
    def __init__(self) -> None:
        self.cache: MutableMapping[str, IPAddress] = {}

    def get_ip(self, headers: Mapping[str, str]) -> IPAddress:
        """Resolve the IP address from the headers."""
        ip_str = headers.get("CF-Connecting-IP")
        if ip_str is None:
            forwards = headers["X-Forwarded-For"].split(",")

            if len(forwards) != 1:
                ip_str = forwards[0]
            else:
                ip_str = headers["X-Real-IP"]

        ip = self.cache.get(ip_str)
        if ip is None:
            ip = ipaddress.ip_address(ip_str)
            self.cache[ip_str] = ip

        return ip


async def fetch_geoloc(
    ip: IPAddress,
    headers: Mapping[str, str] | None = None,
) -> Geolocation | None:
    """Attempt to fetch geolocation data by any means necessary."""
    geoloc = None
    if headers is not None:
        geoloc = _fetch_geoloc_from_headers(headers)

    if geoloc is None:
        geoloc = await _fetch_geoloc_from_ip(ip)

    return geoloc


def _fetch_geoloc_from_headers(headers: Mapping[str, str]) -> Geolocation | None:
    """Attempt to fetch geolocation data from http headers."""
    geoloc = __fetch_geoloc_cloudflare(headers)

    if geoloc is None:
        geoloc = __fetch_geoloc_nginx(headers)

    return geoloc


def __fetch_geoloc_cloudflare(headers: Mapping[str, str]) -> Geolocation | None:
    """Attempt to fetch geolocation data from cloudflare headers."""
    if not all(
        key in headers for key in ("CF-IPCountry", "CF-IPLatitude", "CF-IPLongitude")
    ):
        return None

    country_code = headers["CF-IPCountry"].lower()
    latitude = float(headers["CF-IPLatitude"])
    longitude = float(headers["CF-IPLongitude"])

    return {
        "latitude": latitude,
        "longitude": longitude,
        "country": {
            "acronym": country_code,
            "numeric": country_codes[country_code],
        },
    }


def __fetch_geoloc_nginx(headers: Mapping[str, str]) -> Geolocation | None:
    """Attempt to fetch geolocation data from nginx headers."""
    if not all(
        key in headers for key in ("X-Country-Code", "X-Latitude", "X-Longitude")
    ):
        return None

    country_code = headers["X-Country-Code"].lower()
    latitude = float(headers["X-Latitude"])
    longitude = float(headers["X-Longitude"])

    return {
        "latitude": latitude,
        "longitude": longitude,
        "country": {
            "acronym": country_code,
            "numeric": country_codes[country_code],
        },
    }


async def _fetch_geoloc_from_ip(ip: IPAddress) -> Geolocation | None:
    """Fetch geolocation data based on ip (using ip-api)."""
    if not ip.is_private:
        url = f"http://ip-api.com/line/{ip}"
    else:
        url = "http://ip-api.com/line/"

    response = await http_client.get(
        url,
        params={
            "fields": ",".join(("status", "message", "countryCode", "lat", "lon")),
        },
    )
    if response.status_code != 200:
        log("Failed to get geoloc data: request failed.", Ansi.LRED)
        return None

    status, *lines = response.read().decode().split("\n")

    if status != "success":
        err_msg = lines[0]
        if err_msg == "invalid query":
            err_msg += f" ({url})"

        log(f"Failed to get geoloc data: {err_msg} for ip {ip}.", Ansi.LRED)
        return None

    country_acronym = lines[0].lower()

    return {
        "latitude": float(lines[1]),
        "longitude": float(lines[2]),
        "country": {
            "acronym": country_acronym,
            "numeric": country_codes[country_acronym],
        },
    }


async def log_strange_occurrence(obj: object) -> None:
    pickled_obj: bytes = pickle.dumps(obj)
    uploaded = False

    if app.settings.AUTOMATICALLY_REPORT_PROBLEMS:
        # automatically reporting problems to cmyui's server
        response = await http_client.post(
            url="https://log.cmyui.xyz/",
            headers={
                "Bancho-Version": app.settings.VERSION,
                "Bancho-Domain": app.settings.DOMAIN,
            },
            content=pickled_obj,
        )
        if response.status_code == 200 and response.read() == b"ok":
            uploaded = True
            log(
                "Logged strange occurrence to cmyui's server. "
                "Thank you for your participation! <3",
                Ansi.LBLUE,
            )
        else:
            log(
                f"Autoupload to cmyui's server failed (HTTP {response.status_code})",
                Ansi.LRED,
            )

    if not uploaded:
        # log to a file locally, and prompt the user
        while True:
            if not STRANGE_LOG_DIR.exists():
                STRANGE_LOG_DIR.mkdir(parents=True)
            log_file = STRANGE_LOG_DIR / f"strange_{secrets.token_hex(4)}.db"
            if not log_file.exists():
                break

        log_file.touch(exist_ok=False)
        log_file.write_bytes(pickled_obj)

        log(
            "Logged strange occurrence to" + "/".join(log_file.parts[-4:]),
            Ansi.LYELLOW,
        )
        log(
            "It would be greatly appreciated if you could forward this to the "
            "bancho.py development team. To do so, please email josh@akatsuki.gg",
            Ansi.LYELLOW,
        )


# dependency management


class Version:
    def __init__(self, major: int, minor: int, micro: int) -> None:
        self.major = major
        self.minor = minor
        self.micro = micro

    def __repr__(self) -> str:
        return f"{self.major}.{self.minor}.{self.micro}"

    def __hash__(self) -> int:
        return self.as_tuple.__hash__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented

        return self.as_tuple == other.as_tuple

    def __lt__(self, other: Version) -> bool:
        return self.as_tuple < other.as_tuple

    def __le__(self, other: Version) -> bool:
        return self.as_tuple <= other.as_tuple

    def __gt__(self, other: Version) -> bool:
        return self.as_tuple > other.as_tuple

    def __ge__(self, other: Version) -> bool:
        return self.as_tuple >= other.as_tuple

    @property
    def as_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.micro)

    @classmethod
    def from_str(cls, s: str) -> Version | None:
        split = s.split(".")
        if len(split) == 3:
            return cls(
                major=int(split[0]),
                minor=int(split[1]),
                micro=int(split[2]),
            )

        return None


async def _get_latest_dependency_versions() -> AsyncGenerator[
    tuple[str, Version, Version],
    None,
]:
    """Return the current installed & latest version for each dependency."""
    with open("requirements.txt") as f:
        dependencies = f.read().splitlines(keepends=False)

    # TODO: use asyncio.gather() to do all requests at once? or chunk them

    for dependency in dependencies:
        dependency_name, _, dependency_ver = dependency.partition("==")
        current_ver = Version.from_str(dependency_ver)

        if not current_ver:
            # the module uses some more advanced (and often hard to parse)
            # versioning system, so we won't be able to report updates.
            continue

        # TODO: split up and do the requests asynchronously
        url = f"https://pypi.org/pypi/{dependency_name}/json"
        response = await http_client.get(url)
        json = response.json()

        if response.status_code == 200 and json:
            latest_ver = Version.from_str(json["info"]["version"])

            if not latest_ver:
                # they've started using a more advanced versioning system.
                continue

            yield (dependency_name, latest_ver, current_ver)
        else:
            yield (dependency_name, current_ver, current_ver)


async def check_for_dependency_updates() -> None:
    """Notify the developer of any dependency updates available."""
    updates_available = False

    async for module, current_ver, latest_ver in _get_latest_dependency_versions():
        if latest_ver > current_ver:
            updates_available = True
            log(
                f"{module} has an update available "
                f"[{current_ver!r} -> {latest_ver!r}]",
                Ansi.LMAGENTA,
            )

    if updates_available:
        log(
            "Python modules can be updated with "
            "`python3.11 -m pip install -U <modules>`.",
            Ansi.LMAGENTA,
        )


# sql migrations


async def _get_current_sql_structure_version() -> Version | None:
    """Get the last launched version of the server."""
    res = await app.state.services.database.fetch_one(
        "SELECT ver_major, ver_minor, ver_micro "
        "FROM startups ORDER BY datetime DESC LIMIT 1",
    )

    if res:
        return Version(res["ver_major"], res["ver_minor"], res["ver_micro"])

    return None


async def run_sql_migrations() -> None:
    """Update the sql structure, if it has changed."""
    software_version = Version.from_str(app.settings.VERSION)
    if software_version is None:
        raise RuntimeError(f"Invalid bancho.py version '{app.settings.VERSION}'")

    last_run_migration_version = await _get_current_sql_structure_version()
    if not last_run_migration_version:
        # Migrations have never run before - this is the first time starting the server.
        # We'll insert the current version into the database, so future versions know to migrate.
        await app.state.services.database.execute(
            "INSERT INTO startups (ver_major, ver_minor, ver_micro, datetime) "
            "VALUES (:major, :minor, :micro, NOW())",
            {
                "major": software_version.major,
                "minor": software_version.minor,
                "micro": software_version.micro,
            },
        )
        return  # already up to date (server has never run before)

    if software_version == last_run_migration_version:
        return  # already up to date

    # version changed; there may be sql changes.
    content = SQL_UPDATES_FILE.read_text()

    queries: list[str] = []
    q_lines: list[str] = []

    update_ver = None

    for line in content.splitlines():
        if not line:
            continue

        if line.startswith("#"):
            # may be normal comment or new version
            r_match = VERSION_RGX.fullmatch(line)
            if r_match:
                update_ver = Version.from_str(r_match["ver"])

            continue
        elif not update_ver:
            continue

        # we only need the updates between the
        # previous and new version of the server.
        if last_run_migration_version < update_ver <= software_version:
            if line.endswith(";"):
                if q_lines:
                    q_lines.append(line)
                    queries.append(" ".join(q_lines))
                    q_lines = []
                else:
                    queries.append(line)
            else:
                q_lines.append(line)

    if queries:
        log(
            f"Updating mysql structure (v{last_run_migration_version!r} -> v{software_version!r}).",
            Ansi.LMAGENTA,
        )

    # XXX: we can't use a transaction here with mysql as structural changes to
    # tables implicitly commit: https://dev.mysql.com/doc/refman/5.7/en/implicit-commit.html
    for query in queries:
        try:
            await app.state.services.database.execute(query)
        except pymysql.err.MySQLError as exc:
            log(f"Failed: {query}", Ansi.GRAY)
            log(repr(exc))
            log(
                "SQL failed to update - unless you've been "
                "modifying sql and know what caused this, "
                "please contact @cmyui on Discord.",
                Ansi.LRED,
            )
            raise KeyboardInterrupt from exc
    else:
        # all queries executed successfully
        await app.state.services.database.execute(
            "INSERT INTO startups (ver_major, ver_minor, ver_micro, datetime) "
            "VALUES (:major, :minor, :micro, NOW())",
            {
                "major": software_version.major,
                "minor": software_version.minor,
                "micro": software_version.micro,
            },
        )
