"""Picks the most-used Claude model for the profile card."""

import re


# Turns an ID like claude-opus-5-5 into "Claude Opus 5.5".
def display_name(model_id):
    parts = [p for p in re.sub(r"\[.*\]$", "", model_id).split("-")[1:] if not re.fullmatch(r"\d{8}", p)]
    family = " ".join(p.capitalize() for p in parts if not p.isdigit())
    version = ".".join(p for p in parts if p.isdigit())
    return f"Claude {family} {version}".strip()


# Returns the model with the most tokens, ignoring non-Claude entries.
def top_model(tokens_by_model):
    counts = {m: n for m, n in tokens_by_model.items() if m.startswith("claude-") and n}
    return max(counts, key=counts.get) if counts else None
