"""Package validated simulator rerenders without resizing or changing frames."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("capture", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
meta = json.loads((args.capture / "render_meta.json").read_text())
conditions = {p["condition"]: p for p in meta["panels"]}
names = {"conflict": "conflict", "correct": "correct", "state_live": "repair", "state_early": "early"}
receipts = []
for condition, name in names.items():
    panel = conditions[condition]
    assert panel["reproduction_check"] in ("MATCHES", "OUTCOME_MATCH_STEP_DRIFT"), condition
    if panel["reproduction_check"] == "OUTCOME_MATCH_STEP_DRIFT":
        mismatches = panel["exact_field_mismatches"]
        assert set(mismatches) == {"n_steps"}, mismatches
        assert abs(mismatches["n_steps"]["saved"] - mismatches["n_steps"]["rendered"]) == 1
    assert panel["frame_shape"][:2] == [1024, 1024], panel
    video = args.capture / f"{condition}.mp4"
    target = root / "assets/media" / f"{name}-hd.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-c", "copy",
                    "-movflags", "+faststart", str(target)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(args.capture / f"{condition}.png"),
                    "-frames:v", "1", "-q:v", "2", str(target.with_suffix(".jpg"))], check=True)
    receipts.append({"condition": condition, "source_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                     "published_sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
(root / "assets/data/video-hd-provenance.json").write_text(json.dumps({"capture": meta, "files": receipts}, indent=2) + "\n")
