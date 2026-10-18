"""Answer keys, shipped as plain JSON in `answer_keys/` (installed as `nmrtrain.answer_keys`).

A key holds only calls that a published paper states, each with its source. Every other case has
no key: the feedback then points the member to the paper's own tables and never grades.
"""
from __future__ import annotations

import json
from importlib import resources

# Where a member checks a case that has no key, per key name.
DIPEPTIDE_TABLES = "Table 1 (81%) and Table 2 (98%) of the paper (Petkowski et al. 2024, Sci. Rep. 14, 17083)"
AMINO_ACID_TABLE = "Table 1 of the paper (M. D. Seager et al. 2024, Astrobiology 24, 386)"
CHECK_AGAINST = {
    "capstone": DIPEPTIDE_TABLES,
    "dipeptides": DIPEPTIDE_TABLES,
    "c13_series": DIPEPTIDE_TABLES,
    "amino_acids": AMINO_ACID_TABLE,
}


def available() -> list[str]:
    return sorted(p.name[:-5] for p in resources.files("nmrtrain.answer_keys").iterdir()
                  if p.name.endswith(".json"))


def load(name: str, quiet: bool = False) -> dict:
    """Load a key by name (for example "capstone"). A name with no key file gives an empty key."""
    path = resources.files("nmrtrain.answer_keys").joinpath(f"{name}.json")
    key = json.loads(path.read_text()) if path.is_file() else {"cases": {}}
    key.setdefault("check_against", CHECK_AGAINST.get(name, "the paper's tables"))
    if not quiet:
        if key["cases"]:
            print(f"Published decisions from {key.get('source', 'the paper')}.")
            print(f"  Any other case: check your decision against {key['check_against']}.")
        else:
            print(f"Check your decision against {key['check_against']}.")
    return key


def case(key: dict, case_id: str) -> dict:
    """One case of a key. A case with no published call comes back with call None and where to check it."""
    c = dict(key.get("cases", {}).get(case_id) or {"call": None})
    c.setdefault("sample", case_id.split("-")[0])
    c.setdefault("check_against", key.get("check_against", "the paper's tables"))
    c.setdefault("tolerance_ppm", key.get("tolerance_ppm", 0.05))
    return c
