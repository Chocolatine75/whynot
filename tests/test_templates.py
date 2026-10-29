from pathlib import Path

import pytest

from whynot.create.templates import Template, TemplateError, Variant, load_dir

EXAMPLES = Path(__file__).resolve().parents[1] / "templates" / "examples"


def base(**over):
    data = {"id": "t1", "concept": "C", "persona": "p", "objection": "o",
            "genes": {"format": ["static_1080"], "hook": ["question", "bold_claim"], "cta": ["Go", "Try"]}}
    data.update(over)
    return data


def test_example_templates_load():
    templates = load_dir(EXAMPLES)
    assert templates and templates[0].id == "five_minutes_a_day_v1"
    t = templates[0]
    assert t.space_size() == 1 * 3 * 2 * 3 * 2
    assert t.text("hook", "question") == "No time to learn a language?"
    assert t.text("cta", "Start free") == "Start free"  # no copy entry: the value itself


@pytest.mark.parametrize("over, msg", [
    ({"id": "Bad Id"}, "bad template id"),
    ({"concept": ""}, "missing 'concept'"),
    ({"genes": {"format": ["a"], "hook": ["q"]}}, "missing required genes"),
    ({"genes": {"format": ["a"], "hook": [], "cta": ["x"]}}, "non-empty list"),
    ({"genes": {"format": ["a"], "hook": ["q", "q"], "cta": ["x"]}}, "duplicate options"),
    ({"guards": ["looks_nice"]}, "unknown guards"),
    ({"copy": {"proof": {"x": "y"}}}, "unknown gene"),
    ({"copy": {"hook": {"rhyme": "y"}}}, "unknown hook options"),
])
def test_invalid_templates_are_rejected(over, msg):
    with pytest.raises(TemplateError, match=msg):
        Template.from_dict(base(**over))


def test_genomes_enumerate_the_space_and_sample_is_distinct_and_reproducible():
    t = Template.from_dict(base())
    all_g = list(t.genomes())
    assert len(all_g) == t.space_size() == 4
    assert len({tuple(sorted(g.items())) for g in t.sample(3, seed=1)}) == 3
    assert t.sample(3, seed=1) == t.sample(3, seed=1)
    assert len(t.sample(10)) == 4  # capped at the space size


def test_mutate_changes_exactly_one_gene():
    t = Template.from_dict(base())
    g = {"format": "static_1080", "hook": "question", "cta": "Go"}
    m = t.mutate(g, "hook")
    assert m["hook"] == "bold_claim" and m["cta"] == "Go"
    assert t.mutate(g, "cta", "Try")["cta"] == "Try"
    with pytest.raises(TemplateError, match="single option"):
        t.mutate(g, "format")
    with pytest.raises(TemplateError, match="not an option"):
        t.mutate(g, "cta", "Buy now")
    with pytest.raises(TemplateError):
        t.check({"format": "static_1080", "hook": "question"})


def test_variant_id_depends_only_on_genome():
    g1 = {"hook": "question", "cta": "Go", "format": "static_1080"}
    g2 = {"cta": "Go", "format": "static_1080", "hook": "question"}
    assert Variant("t1", g1).id == Variant("t1", g2, generation=3).id
    assert Variant("t1", g1).id != Variant("t1", {**g1, "cta": "Try"}).id


def test_roundtrip_dict():
    t = Template.from_dict(base(copy={"hook": {"question": "Why?"}}))
    assert Template.from_dict(t.to_dict()) == t


def test_to_dict_is_a_copy():
    """Bug: editing to_dict() output changed the frozen template (found by the evolver tests)."""
    t = Template.from_dict(base(copy={"hook": {"question": "Why?"}}))
    d = t.to_dict()
    d["genes"]["hook"].append("new")
    d["copy"]["hook"]["question"] = "changed"
    assert "new" not in t.genes["hook"] and t.text("hook", "question") == "Why?"
