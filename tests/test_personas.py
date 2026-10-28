from datetime import date

import pytest

from whynot.ingest.adlibrary import CompetitorAd, ReachSlice
from whynot.sim.personas import Persona, allocate, personas_from_reach, reach_cells


def ad(slices):
    return CompetitorAd(id="1", page_id=None, page_name=None, bodies=[], titles=[], start_date=date(2026, 1, 1),
                        stop_date=None, platforms=[], eu_total_reach=None, target_ages=[], target_gender=None,
                        reach_breakdown=[ReachSlice(*s) for s in slices])


def test_allocate_sums_to_n_and_is_proportional():
    counts = allocate({"a": 600, "b": 300, "c": 100}, 10)
    assert counts == {"a": 6, "b": 3, "c": 1}
    assert sum(allocate({"a": 1, "b": 1, "c": 1}, 10).values()) == 10


def test_allocate_is_deterministic_on_ties():
    assert allocate({"a": 1, "b": 1}, 1) == allocate({"b": 1, "a": 1}, 1)


def test_allocate_edge_cases():
    assert allocate({"a": 1}, 0) == {}
    assert allocate({"a": 0}, 5) == {}


def test_reach_cells_sum_across_ads():
    ads = [ad([("FR", "25-34", "female", 100)]), ad([("FR", "25-34", "female", 50), ("FR", "18-24", "male", 10)])]
    assert reach_cells(ads) == {("FR", "25-34", "female"): 150, ("FR", "18-24", "male"): 10}


def test_personas_follow_reach_and_skip_unknown():
    ads = [ad([("FR", "25-34", "female", 700), ("FR", "35-44", "male", 300), ("FR", "25-34", "unknown", 900)])]
    personas = personas_from_reach(ads, 10)
    assert len(personas) == 10
    assert sum(p.gender == "female" for p in personas) == 7
    assert all(p.gender != "unknown" for p in personas)
    assert len({p.id for p in personas}) == 10


def test_personas_need_breakdown():
    with pytest.raises(ValueError):
        personas_from_reach([ad([])], 5)


def test_describe():
    p = Persona("x", "FR", "25-34", "female", ("short on time",))
    assert p.describe() == "a woman aged 25-34 living in FR; short on time"
