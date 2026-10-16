
from pathlib import Path
import shutil
import ast

ROOT = Path(__file__).resolve().parents[1]

CITIES = [
    "bangalore", "chandigarh", "dehradun", "delhi",
    "faridabad", "gaziabad", "greater noida", "gurgaon",
    "hyderabad", "kolkata", "mohali", "mumbai",
    "noida", "panchkula",
]

DATA_ROOT = ROOT / "data" / "cities"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

# Move city folders safely; stop if a destination already exists.
for city in CITIES:
    source = ROOT / city
    folder_name = city.replace(" ", "_")
    destination = DATA_ROOT / folder_name

    if not source.is_dir():
        print(f"SKIP: {source.name} folder not found")
        continue

    if destination.exists():
        print(f"STOP: Destination already exists: {destination}")
        print("Resolve this folder manually before continuing.")
        raise SystemExit(1)

    shutil.move(str(source), str(destination))
    print(f"MOVED: {city} -> data/cities/{folder_name}")

# Create the screenshots directory.
screenshots = ROOT / "images" / "screenshots"
screenshots.mkdir(parents=True, exist_ok=True)
(screenshots / ".gitkeep").touch(exist_ok=True)

# Check Python syntax without executing application code.
src = ROOT / "src"
if src.exists():
    for file in src.rglob("*.py"):
        try:
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except (SyntaxError, UnicodeDecodeError) as error:
            print(f"SYNTAX ERROR: {file}: {error}")
            raise SystemExit(1)

print("\nPython syntax check passed.")
print("Screenshot folder created.")
print("IMPORTANT: Dataset paths have NOT been rewritten.")
print("Update all references before running the application.")
