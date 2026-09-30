#!/usr/bin/env python3
"""Portable, dependency-free source checks. Run from any directory."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "plugins/agent-wiki/plugin.json").read_text())
market = json.loads((root / ".agents/plugins/marketplace.json").read_text())
assert manifest["name"] == market["plugins"][0]["name"]
assert (root / market["plugins"][0]["source"]["path"] / "plugin.json").is_file()
for entry in (root / "plugins/agent-wiki/skills").iterdir():
    text = (entry / "SKILL.md").read_text()
    assert text.startswith("---\n") and f"name: {entry.name}\n" in text
    assert "description: " in text.split("---", 2)[1]
assert (root / "plugins/agent-wiki" / manifest["extensions"]["com.openai"]["onboardingSkill"]).is_file()
result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=root)
raise SystemExit(result.returncode)
