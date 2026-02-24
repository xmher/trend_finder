"""
Romantasy keyword database for trend relevance scoring.

Keywords are organized by category with weights indicating how strongly
they signal romantasy POD potential. Higher weight = stronger signal.
"""

# Weight tiers:
#   5 = dead-on romantasy / POD gold
#   4 = strong romantasy signal
#   3 = solid book/reading community signal
#   2 = adjacent aesthetic / lifestyle
#   1 = loosely related

KEYWORD_DATABASE: dict[str, list[tuple[str, int]]] = {
    # ---- Tropes (the #1 driver of romantasy merch) ----
    "trope": [
        ("enemies to lovers", 5),
        ("friends to lovers", 4),
        ("fated mates", 5),
        ("forced proximity", 5),
        ("only one bed", 5),
        ("grumpy sunshine", 5),
        ("morally grey", 5),
        ("dark romance", 5),
        ("slow burn", 4),
        ("forbidden love", 4),
        ("touch her and die", 5),
        ("who did this to you", 5),
        ("villain romance", 5),
        ("possessive hero", 4),
        ("he falls first", 5),
        ("she falls first", 4),
        ("found family", 4),
        ("chosen one", 3),
        ("dual pov", 3),
        ("love triangle", 3),
        ("second chance romance", 3),
        ("fake dating", 4),
        ("arranged marriage", 4),
        ("mate bond", 5),
        ("rejected mate", 4),
        ("reverse harem", 4),
        ("why choose", 4),
        ("bodyguard romance", 3),
        ("telepathy bond", 4),
    ],

    # ---- Popular Series & Authors (drives merch demand) ----
    "series": [
        ("acotar", 5),
        ("court of thorns and roses", 5),
        ("fourth wing", 5),
        ("iron flame", 5),
        ("onyx storm", 5),
        ("from blood and ash", 5),
        ("crescent city", 5),
        ("throne of glass", 5),
        ("house of flame and shadow", 4),
        ("sarah j maas", 5),
        ("rebecca yarros", 5),
        ("jennifer l armentrout", 4),
        ("kingdom of the wicked", 4),
        ("powerless", 4),
        ("reckless", 4),
        ("haunting adeline", 4),
        ("zodiac academy", 4),
        ("the empyrean", 5),
        ("bride", 4),
        ("ali hazelwood", 3),
        ("penelope douglas", 3),
        ("colleen hoover", 3),
        ("assistant to the villain", 4),
        ("divine rivals", 4),
        ("ruthless vows", 4),
        ("lightlark", 3),
        ("caraval", 3),
        ("serpent and dove", 3),
        ("shatter me", 3),
        ("the cruel prince", 4),
        ("holly black", 4),
        ("elain", 4),
        ("azriel", 5),
        ("rhysand", 5),
        ("feyre", 5),
        ("nesta", 5),
        ("cassian", 4),
        ("xaden riorson", 5),
        ("violet sorrengail", 5),
        ("poppy", 4),
        ("casteel", 4),
    ],

    # ---- BookTok / Reading Community ----
    "community": [
        ("booktok", 5),
        ("bookstagram", 4),
        ("romantasy", 5),
        ("fantasy romance", 5),
        ("romancereaders", 4),
        ("spicy books", 4),
        ("smutty books", 4),
        ("dark fantasy romance", 5),
        ("book boyfriend", 5),
        ("book hangover", 4),
        ("tbr list", 3),
        ("reading wrap up", 3),
        ("book haul", 3),
        ("5 star read", 3),
        ("bookish merch", 5),
        ("bookish candle", 4),
        ("annotating", 3),
        ("tab my book", 3),
        ("spicy scene", 4),
        ("one click", 3),
        ("arc reader", 2),
        ("kindle unlimited", 3),
        ("booktube", 3),
        ("booktwt", 3),
    ],

    # ---- Aesthetics (drives design direction for POD) ----
    "aesthetic": [
        ("dark academia", 4),
        ("cottagecore", 3),
        ("fae aesthetic", 5),
        ("dark fae", 5),
        ("dragon rider", 5),
        ("witchy aesthetic", 4),
        ("gothic romance", 4),
        ("ethereal", 3),
        ("celestial", 3),
        ("dark fantasy", 4),
        ("enchanted forest", 3),
        ("moonlit", 3),
        ("starfall", 4),
        ("night court", 5),
        ("velaris", 5),
        ("wings", 3),
        ("fae ears", 4),
        ("pointed ears", 3),
        ("fantasy map", 3),
        ("sword", 2),
        ("throne", 3),
        ("crown", 3),
        ("castle", 2),
        ("medieval", 2),
    ],

    # ---- Quotes & Phrases (popular for merch) ----
    "quote": [
        ("to whatever end", 5),
        ("i am no bird", 3),
        ("a court of", 4),
        ("fire breathing", 3),
        ("bat boys", 5),
        ("inner circle", 4),
        ("blood and ash", 5),
        ("one more chapter", 4),
        ("just one more chapter", 4),
        ("currently reading", 3),
        ("do not disturb reading", 3),
        ("morally grey book boyfriend", 5),
        ("fictional men", 5),
        ("book lover", 3),
        ("reader girl", 3),
        ("smut reader", 4),
        ("i love morally grey characters", 5),
    ],

    # ---- POD Product Types ----
    "pod_product": [
        ("book shirt", 5),
        ("bookish tshirt", 5),
        ("bookish sweatshirt", 5),
        ("book tote", 5),
        ("bookish sticker", 5),
        ("bookish mug", 5),
        ("book sleeve", 4),
        ("kindle case", 4),
        ("book merch", 5),
        ("reading shirt", 4),
        ("fantasy merch", 4),
        ("book hoodie", 4),
        ("bookish gift", 4),
        ("print on demand", 3),
        ("etsy bookish", 5),
        ("redbubble", 2),
        ("teepublic", 2),
    ],
}


def get_all_keywords() -> list[str]:
    """Return a flat list of all keyword strings."""
    keywords = []
    for entries in KEYWORD_DATABASE.values():
        for kw, _weight in entries:
            keywords.append(kw)
    return keywords


def get_search_queries() -> list[str]:
    """Return a curated list of search queries to use across platforms."""
    # Mix of broad and specific queries for best coverage
    return [
        "romantasy",
        "booktok romantasy",
        "fantasy romance",
        "enemies to lovers",
        "fated mates",
        "morally grey",
        "fourth wing",
        "acotar",
        "sarah j maas",
        "bookish merch",
        "book boyfriend",
        "spicy books",
        "dark romance",
        "touch her and die",
        "grumpy sunshine",
        "only one bed",
        "dark academia books",
        "dragon rider romance",
        "fae romance",
        "bookish tshirt",
    ]


def get_subreddits() -> list[str]:
    """Reddit-specific: subreddits to monitor."""
    return [
        "RomanceBooks",
        "FantasyRomance",
        "romantasy",
        "BookTok",
        "PrintOnDemand",
        "EtsySellers",
    ]
