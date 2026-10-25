"""Check the Lab's Hugging Face models against the public router listing. Free: one GET, no token, no inference.
Prints whether each model and its pinned provider are still live, and whether prices changed.
It never edits data/lab_models.json: a person confirms models there before any live run."""
import json
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config  # noqa: E402

LISTING_URL = "https://router.huggingface.co/v1/models"


def check(registry, listing):
    by_id = {m["id"]: m for m in listing.get("data", [])}
    rows = []
    for m in registry["models"]:
        if m["adapter"] != "hf":
            rows.append((m["key"], "SKIP", "not a Hugging Face model"))
            continue
        provider = next((p for p in by_id.get(m["model_id"], {}).get("providers", [])
                         if p.get("provider") == m["provider"]), None)
        if provider is None:
            rows.append((m["key"], "MISSING", f"{m['model_id']} via {m['provider']} is not listed"))
            continue
        problems = []
        if provider.get("status") != "live":
            problems.append(f"status {provider.get('status')}")
        if not provider.get("supports_structured_output"):
            problems.append("no structured output")
        price = provider.get("pricing") or {}
        listed_in, listed_out = price.get("input"), price.get("output")
        if (listed_in is None or listed_out is None or round(listed_in, 6) != float(m["price_in_per_m"])
                or round(listed_out, 6) != float(m["price_out_per_m"])):
            problems.append(f"price now {listed_in} / {listed_out} per M tokens")
        rows.append((m["key"], "CHANGED" if problems else "OK", "; ".join(problems) or "live, prices match"))
    return rows


def main():
    with open(config.LAB_MODELS_PATH, encoding="utf-8") as f:
        registry = json.load(f)
    listing = requests.get(LISTING_URL, timeout=20).json()
    for key, status, note in check(registry, listing):
        print(f"{status:<8} {key:<10} {note}")


if __name__ == "__main__":
    main()
