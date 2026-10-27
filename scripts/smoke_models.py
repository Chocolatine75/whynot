"""Smoke-test every model whynot depends on. Costs a few cents in total.

Usage:
    uv run python scripts/smoke_models.py              # all checks
    uv run python scripts/smoke_models.py --only spark_text sam_segment

Writes outputs/smoke.json and prints a table. Record what you learn in
docs/META_APIS.md (real model IDs, input types accepted, output formats).
"""

import argparse
import base64
import json
import time
from pathlib import Path

from whynot.config import REPO_ROOT
from whynot.models import SPARK, SPARK_CONTRIBUTOR, WONDER, ModelClient
from whynot.sam import parse

# Public test image (Wikimedia Commons). Only used for smoke tests, never shown in the product.
DEFAULT_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/640px-Cat03.jpg"
OUT = REPO_ROOT / "outputs"


def vision_message(question: str, image_url: str) -> list[dict]:
    return [{"role": "user", "content": [
        {"type": "text", "text": question},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]}]


def build_checks(client: ModelClient, image_url: str) -> dict:
    say_ok = [{"role": "user", "content": "Reply with exactly: OK"}]

    def models_list():
        ids = client.list_meta_models()
        return {"models": ids}

    def spark_text():
        r = client.chat(say_ok, module="smoke", model=SPARK, max_tokens=20)
        return {"reply": r.text, "usd": r.cost.usd}

    def spark_vision():
        r = client.chat(vision_message("Which animal is this? One word.", image_url),
                        module="smoke", model=SPARK, max_tokens=20)
        return {"reply": r.text, "usd": r.cost.usd}

    def contributor_text():
        # Synthetic prompt only: Meta trains on Contributor-tier data.
        r = client.chat(say_ok, module="smoke", model=SPARK_CONTRIBUTOR, max_tokens=20)
        return {"reply": r.text, "usd": r.cost.usd}

    def wonder_text():
        r = client.chat(say_ok, module="smoke", model=WONDER, max_tokens=20)
        return {"reply": r.text, "usd": r.cost.usd}

    def image_generate():
        r = client.image("A plain blue square on a white background", module="smoke", n=1)
        path = OUT / "smoke_image.webp"
        if r.images_b64:
            path.write_bytes(base64.b64decode(r.images_b64[0]))
        return {"images": len(r.images_b64), "saved": str(path.relative_to(REPO_ROOT)), "usd": r.cost.usd}

    def sam_segment():
        r = client.segment(image_url, "cat", module="smoke")
        boxes, masks = parse(r.text)
        return {"boxes": [vars(b) for b in boxes], "masks": [(m.height, m.width, m.encoding) for m in masks],
                "raw_head": r.text[:300], "usd": r.cost.usd}

    def open_text():
        r = client.open_chat(say_ok, module="smoke", max_tokens=20)
        return {"model": client.settings.baseten_model, "reply": r.text, "usd": r.cost.usd}

    def open_vision():
        r = client.open_chat(vision_message("Which animal is this? One word.", image_url),
                             module="smoke", max_tokens=20)
        return {"reply": r.text, "usd": r.cost.usd}

    return {f.__name__: f for f in [models_list, spark_text, spark_vision, contributor_text,
                                    wonder_text, image_generate, sam_segment, open_text, open_vision]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="run only these checks")
    parser.add_argument("--image-url", default=DEFAULT_IMAGE)
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)
    client = ModelClient()
    checks = build_checks(client, args.image_url)
    names = args.only or list(checks)

    results = {}
    for name in names:
        start = time.time()
        try:
            data = checks[name]()
            results[name] = {"ok": True, "seconds": round(time.time() - start, 1), **data}
        except Exception as exc:  # report every failure, keep going
            results[name] = {"ok": False, "seconds": round(time.time() - start, 1),
                             "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        status = "ok  " if results[name]["ok"] else "FAIL"
        detail = results[name].get("reply") or results[name].get("error") or ""
        print(f"{status} {name:<18} {results[name]['seconds']:>5}s  {str(detail)[:90]}")

    total = sum(r.get("usd", 0) for r in results.values())
    print(f"\nTotal cost of this run: ${total:.4f}")
    (OUT / "smoke.json").write_text(json.dumps(results, indent=2, default=str))
    print(f"Details: {Path('outputs') / 'smoke.json'}")


if __name__ == "__main__":
    main()
