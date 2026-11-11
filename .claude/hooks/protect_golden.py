import json
import re
import sys

command = json.load(sys.stdin).get("tool_input", {}).get("command", "").replace("\\", "/").lower()
# Collapse "//" and "/./" so other spellings of a protected path still match.
command = re.sub(r"/(?:\.?/)+", "/", command)
touches_ground_truth = "eval/golden" in command or "labels/pine_editor.csv" in command
refreezes = "eval.freeze" in command and "--check" not in command
if touches_ground_truth or refreezes:
    print(
        "Blocked: the tasks, their lock file and the Pine Editor labels belong to the owner. "
        "Never change them.",
        file=sys.stderr,
    )
    sys.exit(2)
