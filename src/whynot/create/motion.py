"""A static ad brought to life for Reels and Stories (`whynot motion RUN`): 9:16, about 7 s, all code.

Same copy, same real screens, same verified facts as the static ad (its template and genome), animated by the
Remotion `StaticMotion` composition: the headline word by word, the real screen rising and scrolling in a phone,
the layout's fact on its own beat (review and stars, benefits ticked, a number counting up, the objection struck
out), then the call to action. Nothing is generated, so a motion ad costs no model call.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image

from whynot.create.composer import LEGACY_LAYOUT, _style_colours, best_text_colour, hex_to_rgb
from whynot.create.remotion import FPS, render_composition
from whynot.create.templates import Template

SECONDS = 7.0


def _hex(c: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*c)


def key_words(headline: str) -> int:
    """How many of the headline's last words take the accent (as on the static ad)."""
    n = len(headline.split())
    return min(3, max(1, n // 3)) if n >= 3 else 0


def build_props(t: Template, genome: dict[str, str], *, screen: str, second: str | None = None,
                icon: str | None = None, seconds: float = SECONDS) -> dict[str, Any]:
    palette = [hex_to_rgb(c) for c in t.fixed["brand"]["palette"]]
    base, _, _ = _style_colours(genome.get("style", "light"), palette)
    accent = palette[2] if palette[2] != base else best_text_colour(base, palette)
    layout = genome.get("layout") or LEGACY_LAYOUT.get(genome.get("first_shot", ""), "split")
    content = {k: v for k, v in (t.fixed.get("content") or {}).items() if k in ("review", "benefits", "number",
                                                                               "objection")}
    headline = t.text("hook", genome["hook"]).strip()
    return {
        "fps": FPS, "durationInFrames": round(seconds * FPS), "layout": layout, "headline": headline,
        "keyWords": key_words(headline), "proof": t.text("proof", genome["proof"]).strip() if "proof" in genome else "",
        "cta": t.text("cta", genome["cta"]).strip(), "base": _hex(base), "ink": _hex(best_text_colour(base, palette)),
        "look": {"bg": _hex(palette[0]), "fg": _hex(palette[1]), "accent": _hex(accent),
                 "surface": _hex(palette[3] if len(palette) > 3 else palette[0]),
                 "onAccent": _hex(best_text_colour(accent, palette))},
        "screen": screen, **({"second": second} if second else {}), **({"icon": icon} if icon else {}),
        "content": {k: ({"text": v["text"], "rating": int(v.get("rating", 5))} if k == "review" else
                        {"value": v["value"], "label": v["label"]} if k == "number" else
                        {"text": v["text"]} if k == "objection" else list(v)) for k, v in content.items()},
    }


Render = Callable[[str, dict, dict, Path], dict]


def make_motion(run_dir: Path, *, limit: int | None = None, render: Render | None = None,
                say: Callable[[str], None] = print) -> list[dict[str, Any]]:
    """A motion version of every ad in the run's plan (`ads/<variant>.motion.mp4`), listed in `motion.json`."""
    run_dir = Path(run_dir)
    render = render or (lambda comp, props, files, out: render_composition(comp, props, files, out, poster_at=3.0))
    plan = json.loads((run_dir / "plan.json").read_text())
    variants = {v["variant_id"]: v for v in json.loads((run_dir / "variants.json").read_text())}
    templates = {p.stem: Template.load(p) for p in (run_dir / "templates").glob("*.yaml")}
    icon = run_dir / "assets" / "icon.png"
    ids = [a["variant_id"] for s in plan["ad_sets"] for a in s["ads"]][:limit]
    done = []
    for vid in ids:
        v = variants[vid]
        t = templates.get(v["template_id"])
        if t is None:
            continue
        product = t.fixed["product"]
        files: dict[str, Path | Image.Image] = {"screen.png": run_dir / "assets" / product["asset"]}
        if product.get("second") and v["genome"].get("layout") == "two_screens":
            files["second.png"] = run_dir / "assets" / product["second"]
        if icon.exists():
            files["icon.png"] = icon
        props = build_props(t, v["genome"], screen="screen.png", second="second.png" if "second.png" in files else None,
                            icon="icon.png" if icon.exists() else None)
        out = run_dir / "ads" / f"{vid}.motion.mp4"
        facts = render("StaticMotion", props, files, out)
        say(f"  ✓ {out.name}: {facts.get('seconds')} s, layout {props['layout']}")
        done.append({"variant_id": vid, "video": f"ads/{out.name}", "layout": props["layout"], **{
            k: facts[k] for k in ("seconds", "frames") if k in facts}})
    (run_dir / "motion.json").write_text(json.dumps({"videos": done, "usd": 0.0}, indent=1))
    return done
