"""US State, Regional (East/Central/West/South), and Global Country Classification Engine."""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple

# Comprehensive US State mapping (Name -> 2-letter Postal Code)
US_STATES_NAME_TO_CODE: Dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "washington, d.c.": "DC", "florida": "FL",
    "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY",
    "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA",
    "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN",
    "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}

US_STATE_CODE_TO_NAME: Dict[str, str] = {
    v: k.title() for k, v in US_STATES_NAME_TO_CODE.items() if k != "washington, d.c."
}
US_STATE_CODE_TO_NAME["DC"] = "District of Columbia"

# US Regions (Part-of-US targeting)
US_REGIONS: Dict[str, Dict[str, object]] = {
    "east": {
        "label": "US-East (Atlantic / Northeast / Southeast)",
        "states": {
            "ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA",
            "DE", "MD", "DC", "VA", "WV", "NC", "SC", "GA", "FL",
        },
        "centroid": (38.9072, -77.0369),  # Washington DC / Ashburn VA hub
    },
    "central": {
        "label": "US-Central (Midwest / South Central / Texas)",
        "states": {
            "OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO", "ND", "SD",
            "NE", "KS", "KY", "TN", "AL", "MS", "AR", "LA", "OK", "TX",
        },
        "centroid": (36.1627, -90.0000),  # Chicago / Dallas hub
    },
    "west": {
        "label": "US-West (Pacific / Mountain West / Silicon Valley)",
        "states": {
            "WA", "OR", "CA", "NV", "ID", "MT", "WY", "UT", "AZ", "CO",
            "NM", "AK", "HI",
        },
        "centroid": (37.3861, -122.0839),  # Silicon Valley / Seattle / LA hub
    },
    "northeast": {
        "label": "US-Northeast (NY / NJ / New England / PA)",
        "states": {"ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA"},
        "centroid": (40.7128, -74.0060),
    },
    "south": {
        "label": "US-South (TX / FL / GA / VA / NC)",
        "states": {
            "DE", "MD", "DC", "VA", "WV", "NC", "SC", "GA", "FL",
            "KY", "TN", "AL", "MS", "AR", "LA", "OK", "TX",
        },
        "centroid": (32.7767, -96.7970),
    },
    "midwest": {
        "label": "US-Midwest (IL / OH / MI / MN / MO)",
        "states": {"OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO", "ND", "SD", "NE", "KS"},
        "centroid": (41.8781, -87.6298),
    },
}

# Approximate centroids for major US States (for fallback distance calculation)
US_STATE_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "CA": (36.7783, -119.4179),
    "NY": (40.7128, -74.0060),
    "TX": (31.9686, -99.9018),
    "VA": (39.0438, -77.4874),
    "FL": (27.6648, -81.5158),
    "IL": (41.8781, -87.6298),
    "WA": (47.6062, -122.3321),
    "OR": (45.5152, -122.6784),
    "NJ": (40.0583, -74.4057),
    "GA": (33.7490, -84.3880),
    "OH": (39.9612, -82.9988),
    "PA": (39.9526, -75.1652),
    "MA": (42.3601, -71.0589),
    "AZ": (33.4484, -112.0740),
    "CO": (39.7392, -104.9903),
    "NV": (36.1699, -115.1398),
    "UT": (40.7608, -111.8910),
    "NC": (35.2271, -80.8431),
    "MI": (42.3314, -83.0458),
    "MO": (38.6270, -90.1994),
    "MD": (39.2904, -76.6122),
    "DC": (38.9072, -77.0369),
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points on Earth in kilometers."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def normalize_us_state(region_str: str) -> str:
    """Convert a region name (e.g. 'California' or 'CA') into a 2-letter US state code."""
    if not region_str:
        return ""
    clean = region_str.strip()
    upper = clean.upper()
    if upper in US_STATE_CODE_TO_NAME:
        return upper
    lower = clean.lower()
    if lower in US_STATES_NAME_TO_CODE:
        return US_STATES_NAME_TO_CODE[lower]
    for name, code in US_STATES_NAME_TO_CODE.items():
        if name in lower:
            return code
    return ""


def classify_us_region(state_code: str, lon: Optional[float] = None) -> str:
    """Classify a US server into 'east', 'central', or 'west'."""
    st = (state_code or "").upper()
    if st in US_REGIONS["east"]["states"]:
        return "east"
    if st in US_REGIONS["central"]["states"]:
        return "central"
    if st in US_REGIONS["west"]["states"]:
        return "west"
    # Fallback by longitude if state is unknown
    if lon is not None:
        if lon >= -83.0:
            return "east"
        elif lon >= -104.0:
            return "central"
        else:
            return "west"
    return "unknown"


def match_us_region(server: dict, target_region: str) -> bool:
    """Check if a US server belongs to a requested US region (e.g. east, west, central, south, northeast, midwest, all)."""
    if server.get("cc", "").upper() != "US":
        return False
    reg = target_region.strip().lower().replace("us-", "").replace("us_", "")
    if reg in ("all", "any", "us", "*"):
        return True
    if reg not in US_REGIONS:
        return False
    allowed_states = US_REGIONS[reg]["states"]
    state_code = server.get("state_code") or normalize_us_state(server.get("region", ""))
    if state_code and state_code in allowed_states:
        return True
    # Coordinate fallback for main 3 regions
    if not state_code and reg in ("east", "central", "west"):
        inferred = classify_us_region("", server.get("lon"))
        return inferred == reg
    return False

