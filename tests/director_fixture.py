"""A valid creative-director answer for the strategy fixture (reused by pipeline tests)."""


def director_json(angles=("southern_accent", "listen_first", "five_minutes", "free_start")) -> dict:
    ideas = {
        "southern_accent": ("Speak Vietnamese the way your family does, with the Southern accent.",
                            {"family": "Talk like your family does",
                             "accent": "Pick the Northern or Southern accent"}),
        "listen_first": ("Train your ear before you ever have to speak.",
                         {"ear": "Train your ear first", "listen": "Listen, guess, then read"}),
        "five_minutes": ("Short real-life lessons that fit a commute before the trip.",
                         {"commute": "Fit a lesson into your commute", "trip": "Order coffee in Hanoi next month"}),
        "free_start": ("Try the whole method for free before deciding.",
                       {"free": "Start learning for free", "try": "Try it free tonight"}),
    }
    # each concept in its own words (the director refuses a phrase shared by more than 2 concepts)
    bodies = {
        "southern_accent": {"short": "Pick the Southern accent and hear it every day, the way it sounds at home.",
                            "story": "Grandma talks fast, in the South's tones. Hear her way first, then answer."},
        "listen_first": {"short": "Hear a real phrase, guess it, then read it. Your ear leads the way.",
                         "story": "Before speaking comes hearing: natural voices, your guess, then the words."},
        "five_minutes": {"short": "Ten quiet minutes on the train add up before the trip to Hanoi.",
                         "story": "Coffee orders, taxis, greetings: small real moments, one ride at a time."},
        "free_start": {"short": "No card needed to begin. See if the method suits you tonight.",
                       "story": "Open it, try a lesson, decide later. It costs nothing to find out."},
    }
    return {"templates": [{
        "angle": a,
        "concept": ideas[a][0],
        "hooks": ideas[a][1],
        "bodys": bodies[a],
        "titles": {"main": "Learn Vietnamese the way it sounds"},
        "proofs": {"accents": "Northern or Southern accent", "none": ""},
        "ctas": {"INSTALL_MOBILE_APP": "Start free", "LEARN_MORE": "See how it works"},
        "first_shots": ["app_screen", "result_card"],
        "claims_used": ["accents", "free"],
    } for a in angles]}


FRENCH = {
    "southern_accent": ("Parler vietnamien comme votre famille, avec l’accent du Sud.",
                        {"family": "Parlez comme votre famille", "accent": "Choisissez l’accent du Nord ou du Sud"}),
    "listen_first": ("Entraîner l’oreille avant d’avoir à parler.",
                     {"ear": "Entraînez d’abord votre oreille", "listen": "Écoutez, devinez, puis lisez"}),
}


def director_json_fr(angles=("southern_accent", "listen_first")) -> dict:
    return {"templates": [{
        "angle": a, "concept": FRENCH[a][0], "hooks": FRENCH[a][1],
        "bodys": {"short": "Des leçons courtes, tirées de la vraie vie. Choisissez l’accent du Nord ou du Sud.",
                  "story": "Apprenez le vietnamien comme il se parle : écoutez d’abord, parlez ensuite. "
                           "Gratuit pour commencer."},
        "titles": {"main": "Le vietnamien tel qu’il se parle"},
        "proofs": {"accents": "Accent du Nord ou du Sud", "none": ""},
        "ctas": {"INSTALL_MOBILE_APP": "Commencer", "LEARN_MORE": "Voir comment"},
        "first_shots": ["app_screen", "result_card"], "claims_used": ["accents", "free"],
    } for a in angles]}
