"""A valid strategy answer for the test app, built from its real sources (reused by pipeline tests)."""

from datetime import date

from whynot.ingest.adlibrary import CompetitorAd
from whynot.ingest.appstore import AppProfile, Review

REVIEWS = [
    Review("101", 2, "disappointing", "The app doesn't hear you correctly. Very expensive subscription plan.", "1.2",
           "2026-10-19"),
    Review("102", 5, "Great for heritage speakers",
           "I appreciate the southern dialect, which makes this app stand out.", "1.2", "2026-10-22"),
    Review("103", 4, "Short lessons", "Five minutes a day fits my commute and I actually keep my streak.", "1.2",
           "2026-10-20"),
]
APP = AppProfile(
    app_id="1234567890", name="LinguaApp: Learn Vietnamese", seller="Lingua Ltd", bundle_id="com.lingua",
    store_url="https://apps.apple.com/us/app/linguaapp/id1234567890",
    description="Learn Vietnamese the way it sounds. Short real-life lessons. Choose Northern or Southern accent. "
                "Train your ear before reading the transcript. Free to start.",
    genres=["Education"], price=0.0, currency="USD", rating=4.4, rating_count=120, screenshot_urls=[], icon_url=None,
    reviews=REVIEWS)
ADS = [
    CompetitorAd("900", "p1", "Rival Lingo", ["Speak Vietnamese in 10 minutes a day. Start free."], [],
                 date(2026, 5, 1), None, [], None, [], None),
    CompetitorAd("901", "p2", "Other App", ["Tired of textbooks? Learn with native speakers."], [],
                 date(2026, 9, 1), date(2026, 9, 4), [], None, [], None),
]
COUNTRIES = ["FR", "GB"]


def strategy_json() -> dict:
    return {
        "positioning": "For busy learners who want to speak, not read: real Vietnamese, the way it sounds.",
        "objections": [
            {"id": "speech_recognition", "text": "Will it even understand me?",
             "answer": "Show listening-first lessons you can do without speaking.",
             "evidence": [{"ref": "review:101", "quote": "The app doesn't hear you correctly"}]},
            {"id": "too_expensive", "text": "Another expensive subscription",
             "answer": "Free to start.",
             "evidence": [{"ref": "review:101", "quote": "Very expensive subscription plan"}]},
            {"id": "no_time", "text": "I don't have time to study",
             "answer": "Short real-life lessons.",
             "evidence": [{"ref": "ad:900", "quote": "Speak Vietnamese in 10 minutes a day"}]},
        ],
        "personas": [
            {"id": "heritage_learner", "name": "Heritage learner", "description": "Grew up hearing Vietnamese at home.",
             "age_min": 18, "age_max": 34, "gender": "all", "countries": ["FR", "GB"],
             "motivations": ["talk with family"], "objections": ["speech_recognition"]},
            {"id": "busy_traveller", "name": "Busy traveller", "description": "Going to Vietnam soon.",
             "age_min": 25, "age_max": 54, "gender": "all", "countries": ["GB"],
             "motivations": ["get around"], "objections": ["no_time", "too_expensive"]},
        ],
        "angles": [
            {"id": "southern_accent", "idea": "The app that speaks like your family: Southern accent included.",
             "persona": "heritage_learner", "objection": None, "competitors_use_it": False,
             "evidence": [{"ref": "review:102", "quote": "southern dialect, which makes this app stand out"}]},
            {"id": "listen_first", "idea": "Train your ear first.", "persona": "heritage_learner",
             "objection": "speech_recognition", "competitors_use_it": False,
             "evidence": [{"ref": "store", "quote": "Train your ear before reading the transcript"}]},
            {"id": "five_minutes", "idea": "Five minutes on the commute.", "persona": "busy_traveller",
             "objection": "no_time", "competitors_use_it": True,
             "evidence": [{"ref": "review:103", "quote": "Five minutes a day fits my commute"}]},
            {"id": "free_start", "idea": "Start free, no card.", "persona": "busy_traveller",
             "objection": "too_expensive", "competitors_use_it": True,
             "evidence": [{"ref": "ad:900", "quote": "Start free."}, {"ref": "store", "quote": "Free to start"}]},
        ],
        "claims": [
            {"id": "accents", "text": "Choose a Northern or Southern accent",
             "evidence": {"ref": "store", "quote": "Choose Northern or Southern accent"}},
            {"id": "free", "text": "Free to start", "evidence": {"ref": "store", "quote": "Free to start"}},
            {"id": "short_lessons", "text": "Short real-life lessons",
             "evidence": {"ref": "store", "quote": "Short real-life lessons"}},
        ],
        "notes": ["Speech recognition complaints: avoid promising perfect pronunciation feedback."],
    }
