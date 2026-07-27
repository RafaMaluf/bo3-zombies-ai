# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE_PATTERN = re.compile(r"Related image:\s+([^\s]+)")
SECTION_PATTERN = re.compile(r"(?m)^## (.+?)\s*$")


@dataclass(frozen=True, slots=True)
class DocumentPlan:
    path: str
    title: str
    category: str
    summary: str
    sections: tuple[str, ...]
    prefix: str = ""


@dataclass(frozen=True, slots=True)
class MapPlan:
    documents: tuple[DocumentPlan, ...]
    supplemental_sources: tuple[str, ...] = ()


def document(
    path: str,
    title: str,
    category: str,
    summary: str,
    *sections: str,
    prefix: str = "",
) -> DocumentPlan:
    return DocumentPlan(path, title, category, summary, sections, prefix.strip())


NACHT_SETUP = """
## Zombies Chronicles setup

Nacht der Untoten has no power switch and no native Pack-a-Punch machine.
The playable building has only three connected areas: the spawn room, the
Help / Mystery Box room, and the upstairs room. Each route between them costs
1000 points.

The Zombies Chronicles version adds Gobblegum machines, Mule Kick and a
Wunderfizz upstairs. The Mystery Box can provide the Thundergun, Ray Gun,
Ray Gun Mark II and Monkey Bombs. The sniper cabinet upstairs sells the Locus
for 5000 points.

Explosive barrels outside the playable area can damage nearby zombies. There
are no powered traps or buildables.
"""

VERRUCKT_SETUP = """
## Power, layout and Pack-a-Punch

In co-op, the team starts split between two sides of the asylum. Open doors
along either route until reaching the central power room, then use the power
switch. Turning on power opens the dividing door in spawn and connects the
map into one large loop.

Verrückt has no native Pack-a-Punch machine. A weapon can only be upgraded
through a Gobblegum effect that provides Pack-a-Punch access.

## Traps and Wonder Weapon

Three electric traps cost 1000 points each: one by the M1 Carbine doorway,
one by the Double-Barreled Shotgun doorway, and one under the bridge near the
power switch. They can also down players who remain in the electricity.

In the Zombies Chronicles version, the Wunderwaffe DG-2 comes from the
Mystery Box. Wunderfizz machines provide perks beyond the four fixed machines.
"""

SHI_SETUP = """
## Layout, perks and Pack-a-Punch

Shi No Numa has no power switch and no native Pack-a-Punch machine. The
central building connects to four areas: Storage, Doctor's Quarters, Fishing
Hut and Comm Room. Opening a hut reveals a random perk machine, so the perk
assigned to each hut changes every match.

The Wunderwaffe DG-2, Ray Gun Mark II and Monkey Bombs are available from the
Mystery Box in the Zombies Chronicles version.

## Traps and transport

Each outer hut has a 1000-point electric trap. The Flogger outside the central
building also costs 1000 points and launches zombies away. The zipline links
Doctor's Quarters to the central building but does not count as a trap.
"""

SHANG_PLAYER_REQUIREMENT = """
## Player-count requirement

The supported player counts are:

- 4 players in an unmodified Black Ops III / Zombies Chronicles match.
- 1 player in solo when a compatible Solo Easter Egg mod is enabled. Solo is not supported by the vanilla map.
- Never 2 or 3 players; the simultaneous co-op steps cannot be completed with those group sizes.

When someone asks whether the quest works with fewer than four players, the
complete answer is: only solo with the mod. This guide describes the
four-player vanilla route.
"""


PLANS: dict[str, MapPlan] = {
    "nacht_der_untoten": MapPlan(
        documents=(
            document(
                "general.md",
                "Nacht der Untoten overview",
                "general",
                "Zombies Chronicles setup, layout, lack of power and Pack-a-Punch, weapons, perks, and basic survival features.",
                "Intro",
                prefix=NACHT_SETUP,
            ),
            document(
                "samantha_dolls.md",
                "Samantha dolls",
                "side_ee",
                "How to activate the four buttons, find the Samantha doll, shoot all eight spawned dolls, and claim the Max Ammo reward.",
                "Side easter egg - Samantha's dolls",
            ),
            document(
                "music_ee.md",
                "Undone secret song",
                "music_ee",
                "How to activate the Undone secret song by shooting the red explosive barrels outside Nacht der Untoten.",
                "Side easter egg - Secret Song",
            ),
            document(
                "achievement.md",
                "Nacht der Untoten achievement",
                "achievement",
                "How to complete the I said we're CLOSED! achievement.",
                "Achievement",
            ),
        ),
        supplemental_sources=("https://www.reddit.com/r/CODZombies/wiki/nacht-der-untoten/",),
    ),
    "verruckt": MapPlan(
        documents=(
            document(
                "general.md",
                "Verrückt overview",
                "general",
                "Power, split-spawn layout, lack of native Pack-a-Punch, electric traps, Wunderfizz, and Wunderwaffe DG-2.",
                "Intro",
                prefix=VERRUCKT_SETUP,
            ),
            document(
                "samantha_dolls.md",
                "Samantha dolls",
                "side_ee",
                "How to enter the 9-3-5 toilet sequence, find ten timed Samantha dolls, and claim the reward.",
                "Secret easter egg - Samantha's dolls",
            ),
            document(
                "music_ee.md",
                "Lullaby for a Dead Man",
                "music_ee",
                "How to activate Lullaby for a Dead Man using the toilet in the bathroom beside the power room.",
                "Side easter egg - Secret song",
            ),
            document(
                "achievement.md",
                "Verrückt achievement",
                "achievement",
                "How to complete the Acted Alone achievement.",
                "Achievement",
            ),
        ),
        supplemental_sources=("https://www.reddit.com/r/CODZombies/wiki/verruckt/",),
    ),
    "shi_no_numa": MapPlan(
        documents=(
            document(
                "general.md",
                "Shi No Numa overview",
                "general",
                "Random perk huts, lack of power and Pack-a-Punch, Wunderwaffe DG-2, electric traps, Flogger, and zipline.",
                "Some things",
                prefix=SHI_SETUP,
            ),
            document(
                "samantha_dolls.md",
                "Samantha dolls",
                "side_ee",
                "How to shoot four Fishing Hut plates with the starting pistol, destroy the dolls, and claim the Max Ammo reward.",
                "Side easter egg - Samantha's dolls",
            ),
            document(
                "music_ee.md",
                "The One secret song",
                "music_ee",
                "How to activate The One using the telephone in the Comm Room.",
                "Side easter egg - Secret song",
            ),
            document(
                "traps_achievement.md",
                "It's a Trap! achievement",
                "achievement",
                "How to use the Flogger and electric traps in one round for the It's a Trap! achievement.",
                "Achievement",
            ),
        ),
        supplemental_sources=("https://www.reddit.com/r/CODZombies/wiki/shi-no-numa/",),
    ),
    "kino_der_toten": MapPlan(
        documents=(
            document(
                "general.md",
                "Kino der Toten overview",
                "general",
                "Overview of the Zombies Chronicles version of Kino der Toten.",
                "Introduction",
            ),
            document(
                "power_pap.md",
                "Power, teleporter and Pack-a-Punch",
                "pap",
                "How to reach the stage, turn on power, link the teleporter, enter the projector room, and use Pack-a-Punch.",
                "Activating the power - Getting to the Pack-a-Punch",
            ),
            document(
                "film_reels.md",
                "Film reels",
                "side_ee",
                "Where to find the film reels in the random teleporter rooms and how to play them in the projector room.",
                "Side easter egg - Movie projector",
            ),
            document(
                "paintings.md",
                "Character paintings",
                "side_ee",
                "Where to find and interact with the character paintings and the hidden blank portrait.",
                "Side easter egg - Paintings",
            ),
            document(
                "rocket_figurine.md",
                "Rocket shield figurine",
                "side_ee",
                "How to reveal and collect the rocket figurine near the stage.",
                "Side easter egg - Rocket figurine",
            ),
            document(
                "samantha_sorrow.md",
                "Samantha's Sorrow",
                "side_ee",
                "How to complete the Samantha doll hunt and receive the Max Ammo reward on Kino der Toten.",
                "Side easter egg - Samantha's Sorrow",
            ),
            document(
                "music_ee.md",
                "115 secret song",
                "music_ee",
                "Locations of the three meteorite fragments used to activate the song 115.",
                "Side easter egg - Secret Song",
            ),
            document(
                "achievement.md",
                "Kino der Toten achievement",
                "achievement",
                "How to complete the Kino der Toten map achievement.",
                "Achievement",
            ),
        ),
        supplemental_sources=(
            "https://www.reddit.com/r/CODZombies/comments/4p0mbg/kino_der_toten_complete_map_breakdown/",
        ),
    ),
    "ascension": MapPlan(
        documents=(
            document(
                "general.md",
                "Ascension overview",
                "general",
                "Overview of Ascension, its lunar landers, special equipment, quests, and special rounds.",
                "Introduction",
            ),
            document(
                "power_pap.md",
                "Power, lunar landers and Pack-a-Punch",
                "pap",
                "How to turn on power, use all lunar landers, launch the rocket, and open Pack-a-Punch.",
                "Preparation - Activating Power & Accessing Pack-a-Punch",
            ),
            document(
                "main_ee.md",
                "Ascension main easter egg",
                "main_ee",
                "Complete four-player Ascension main quest, including Gersh devices, pressure plates, LUNA letters, nodes, and final weapons.",
                "Main easter egg quest",
                "TL;DR Cheatsheet for the main quest",
            ),
            document(
                "samantha_sorrow.md",
                "Samantha's Sorrow",
                "side_ee",
                "How to use Gersh Devices, find the dolls, and earn the Samantha's Sorrow reward.",
                "Side easter egg - Samantha's sorrow",
            ),
            document(
                "music_ee.md",
                "Abracadavre secret song",
                "music_ee",
                "Locations of the three teddy bears used to activate Abracadavre.",
                "Side easter egg - Teddy bears",
            ),
            document(
                "space_monkeys.md",
                "Space monkey rounds",
                "special_round",
                "How Ascension's space monkey rounds work, how perks are attacked, and how to earn a free perk.",
                "Information - Special rounds",
            ),
            document(
                "achievements.md",
                "Ascension achievements",
                "achievement",
                "Requirements and practical steps for Ascension achievements.",
                "Achievements",
            ),
        ),
        supplemental_sources=("https://www.reddit.com/r/CODZombies/wiki/ascension/",),
    ),
    "shangri_la": MapPlan(
        documents=(
            document(
                "general.md",
                "Shangri-La overview",
                "general",
                "Overview of Shangri-La, its quest, traps, special zombies, and 31-79 JGb215 wonder weapon.",
                "Introduction",
            ),
            document(
                "power_pap.md",
                "Power and pressure-plate Pack-a-Punch",
                "pap",
                "How to turn on both power switches and coordinate the four pressure plates to access Pack-a-Punch.",
                "Preparation - Activating Power - Accessing Pack-a-Punch",
            ),
            document(
                "main_ee.md",
                "Shangri-La main easter egg",
                "main_ee",
                "The main quest supports 4 players in vanilla or 1 player with a Solo Easter Egg mod, never 2 or 3; includes the complete four-player Time Travel Will Tell route.",
                "Main easter egg quest - Part 1",
                "Main easter egg quest - Part 2",
                "TL;DR Cheatsheet for the main easter egg",
                prefix=SHANG_PLAYER_REQUIREMENT,
            ),
            document(
                "music_ee.md",
                "Pareidolia secret song",
                "music_ee",
                "Locations of the three meteorite fragments used to activate Pareidolia.",
                "Side easter egg - Secret song",
            ),
            document(
                "samantha_hide_and_seek.md",
                "Samantha hide and seek",
                "side_ee",
                "How to activate and complete the timed Samantha doll hide-and-seek quest.",
                "Side easter egg - Samantha Hide and Seek",
            ),
            document(
                "achievements.md",
                "Shangri-La achievements",
                "achievement",
                "Requirements and practical steps for Shangri-La achievements.",
                "Achievements",
            ),
        ),
        supplemental_sources=("https://www.speedrun.com/bo3zombies/resources/fiusc",),
    ),
    "moon": MapPlan(
        documents=(
            document(
                "general.md",
                "Moon overview",
                "general",
                "Overview of Area 51, Griffin Station, excavators, equipment, wonder weapons, quests, and low-gravity systems.",
                "Introduction",
            ),
            document(
                "power_pap.md",
                "Power, Area 51 teleporter and Pack-a-Punch",
                "pap",
                "How to leave Area 51, turn on power at Griffin Station, return to No Man's Land, and use Pack-a-Punch.",
                "Preparation - Activating the Power - Accessing Pack-a-Punch",
            ),
            document(
                "main_ee.md",
                "Moon main easter egg",
                "main_ee",
                "Complete Moon main quest, including computer colors, Hacker terminals, excavator tunnel, pyramid souls, Samantha Says, plates, QED steps, and rockets.",
                "Main easter egg quest - Part 1",
                "Main easter egg quest - Part 2",
                "TL;DR - Cheatsheet for the main easter egg",
            ),
            document(
                "hacker.md",
                "Hacker",
                "equipment",
                "Hacker spawn locations and all of its uses, including doors, windows, power-ups, mystery box, perks, excavators, and Pack-a-Punch protection.",
                "Equipment - Hacker Tool",
            ),
            document(
                "pes.md",
                "P.E.S.",
                "equipment",
                "Where to obtain the P.E.S. suit and when it is required for oxygen.",
                "Equipment - P.E.S",
            ),
            document(
                "qed.md",
                "Q.E.D.",
                "equipment",
                "How to obtain and use Quantum Entanglement Devices and what kinds of effects they can produce.",
                "Equipment - Q.E.D",
            ),
            document(
                "samantha_sorrow.md",
                "Samantha's Sorrow",
                "side_ee",
                "How to complete Moon's Samantha doll quest and claim the reward.",
                "Side easter egg - Samantha's sorrow",
            ),
            document(
                "space_dog.md",
                "Space dog",
                "side_ee",
                "How to spawn and feed the space dog around Moon.",
                "Side easter egg - Space Dog",
            ),
            document(
                "music_ee_1.md",
                "Coming Home secret song",
                "music_ee",
                "How to activate Moon's first secret song.",
                "Side easter egg - Secret song 1",
            ),
            document(
                "music_ee_2.md",
                "Nightmare secret song",
                "music_ee",
                "How to activate Moon's second secret song.",
                "Side easter egg - Secret song 2",
            ),
            document(
                "music_ee_3.md",
                "Re-Damned secret song",
                "music_ee",
                "How to activate Moon's third secret song.",
                "Side easter egg - Secret song 3",
            ),
            document(
                "achievements.md",
                "Moon achievements",
                "achievement",
                "Requirements and practical steps for Moon achievements.",
                "Achievements",
            ),
        ),
    ),
    "origins": MapPlan(
        documents=(
            document(
                "general.md",
                "Origins overview",
                "general",
                "Overview of Origins, generators, staffs, buildables, challenges, quests, and special systems.",
                "Introduction",
            ),
            document(
                "power_pap.md",
                "Generators and Pack-a-Punch",
                "pap",
                "Locations of all six generators, how to activate and defend them, and how they unlock Pack-a-Punch.",
                "Preparation - Accessing Pack-a-Punch",
            ),
            document(
                "staff_setup.md",
                "Staff crafting setup",
                "wonder_weapon",
                "How to find the black disk and gramophone, open the excavation stairs, and prepare the four staff altars.",
                "Preparation - Setting-up staff crafting",
            ),
            document(
                "fire_staff.md",
                "Fire Staff and Kagutsuchi's Blood",
                "wonder_weapon",
                "How to collect the Fire Staff parts, disk and crystal, craft it, solve both upgrade puzzles, and prepare Kagutsuchi's Blood.",
                "Preparation - Fire Staff",
                "Preparation - Kagutsuchi's blood (Upgraded fire staff)",
            ),
            document(
                "ice_staff.md",
                "Ice Staff and Ull's Arrow",
                "wonder_weapon",
                "How to collect the Ice Staff parts, disk and crystal, craft it, solve both upgrade puzzles, and prepare Ull's Arrow.",
                "Preparation - Ice staff",
                "Preparation - Ull's Arrow (Upgraded ice staff)",
            ),
            document(
                "lightning_staff.md",
                "Lightning Staff and Kimat's Bite",
                "wonder_weapon",
                "How to collect the Lightning Staff parts, disk and crystal, craft it, solve both upgrade puzzles, and prepare Kimat's Bite.",
                "Preparation - Lightning staff",
                "Preparation - Kimat's bite (Upgraded lightning staff)",
            ),
            document(
                "wind_staff.md",
                "Wind Staff and Boreas' Fury",
                "wonder_weapon",
                "How to collect the Wind Staff parts, disk and crystal, craft it, solve both upgrade puzzles, and prepare Boreas' Fury.",
                "Preparation - Wind staff",
                "Preparation - Borea's Fury (Upgraded wind staff)",
            ),
            document(
                "staff_final_upgrade.md",
                "Final staff upgrade stage",
                "wonder_weapon",
                "How to align the excavation rings, shoot the orb, place a prepared staff in the Crazy Place, and charge it with zombie souls.",
                "Preparation - Final upgrade stage for all staffs",
            ),
            document(
                "main_ee.md",
                "Origins main easter egg",
                "main_ee",
                "Complete Little Lost Girl, including upgraded staffs, robot pedestals, G-Strike seal, Odin strike, elemental fists, Maxis Drone, Crazy Place, and final portal.",
                "Main easter egg quest",
                "TL;DR Cheat sheet for the main quest",
            ),
            document(
                "g_strike.md",
                "G-Strike",
                "equipment",
                "How to purify the stone tablet with melee kills and convert Monkey Bombs into G-Strike beacons.",
                "Equipment - G-Strike",
            ),
            document(
                "maxis_drone.md",
                "Maxis Drone",
                "equipment",
                "Locations of all three Maxis Drone parts and where to build it.",
                "Equipment - Maxis Drone",
            ),
            document(
                "one_inch_punch.md",
                "One Inch Punch",
                "equipment",
                "How to fill the four robot-foot soul chests and claim the One Inch Punch from the reward chest.",
                "Equipment - One inch punch",
            ),
            document(
                "shield.md",
                "Zombie Shield",
                "equipment",
                "Locations of all three Zombie Shield parts and the available crafting tables.",
                "Equipment - Shield",
            ),
            document(
                "shovel_upgrades.md",
                "Shovel, Golden Shovel and Golden Helmet",
                "equipment",
                "How digging works, how to earn the Golden Shovel and Golden Helmet, and how red dig sites appear.",
                "Equipment - Shovel, Golden Shovel, Golden Helmet and red Dig ups",
            ),
            document(
                "challenges.md",
                "Origins challenges",
                "challenge",
                "Challenge objectives, progress tracking, and rewards available from the challenge chests.",
                "Challenges",
            ),
            document(
                "music_ee_1.md",
                "Archangel secret song",
                "music_ee",
                "Locations used to activate Archangel.",
                "Side easter egg - Secret song",
            ),
            document(
                "music_ee_2.md",
                "Shepherd of Fire secret song",
                "music_ee",
                "How to activate Shepherd of Fire.",
                "Side easter egg - Secret song 2",
            ),
            document(
                "music_ee_3.md",
                "Aether secret song",
                "music_ee",
                "How to activate Aether.",
                "Side easter egg - Secret song 3",
            ),
            document(
                "samantha_sorrow.md",
                "Samantha's Sorrow",
                "side_ee",
                "How to complete the Samantha doll side quest and claim its reward.",
                "Side easter egg - Samantha sorrow",
            ),
            document(
                "free_magna_collider.md",
                "Free Magna Collider",
                "side_ee",
                "How to obtain the free Magna Collider weapon.",
                "Side easter egg - Free MagnaCollider",
            ),
            document(
                "free_zombie_blood.md",
                "Free Zombie Blood",
                "side_ee",
                "How to trigger the free Zombie Blood power-up.",
                "Side easter egg - Free Zombie Blood",
            ),
            document(
                "achievements.md",
                "Origins achievements",
                "achievement",
                "Requirements and practical steps for Origins achievements.",
                "Achievements",
            ),
        ),
    ),
}


def split_sections(markdown: str) -> dict[str, str]:
    matches = list(SECTION_PATTERN.finditer(markdown))
    sections: dict[str, str] = {}
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(markdown)
        sections[match.group(1).strip()] = markdown[match.start() : end].strip()
    return sections


def curate_map(map_dir: Path, plan: MapPlan) -> None:
    source_path = map_dir / "source_guide.md"
    source = source_path.read_text(encoding="utf-8")
    sections = split_sections(source)
    index = json.loads((map_dir / "index.json").read_text(encoding="utf-8"))
    provenance_path = map_dir / "sources.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

    rendered_documents: dict[str, str] = {}
    files: list[dict[str, str]] = []
    for spec in plan.documents:
        missing = [heading for heading in spec.sections if heading not in sections]
        if missing:
            raise ValueError(f"{map_dir.name}/{spec.path}: missing sections {missing}")
        parts = [f"# {spec.title}"]
        if spec.prefix:
            parts.append(spec.prefix)
        parts.extend(sections[heading] for heading in spec.sections)
        content = "\n\n".join(parts).strip() + "\n"
        rendered_documents[spec.path] = content
        files.append(
            {
                "path": spec.path,
                "category": spec.category,
                "summary": spec.summary,
            }
        )

    image_documents: dict[str, str] = {}
    for document_path, content in rendered_documents.items():
        for image_path in IMAGE_PATTERN.findall(content):
            image_documents.setdefault(image_path, document_path)

    for document_path, content in rendered_documents.items():
        (map_dir / document_path).write_text(content, encoding="utf-8")

    kept_images: list[dict[str, object]] = []
    for image in provenance.get("images", []):
        image_path = str(image.get("path", ""))
        document_path = image_documents.get(image_path)
        if document_path:
            image["document"] = document_path
            kept_images.append(image)
            continue
        orphan = map_dir / image_path
        if orphan.is_file():
            orphan.unlink()

    original_sources = provenance.get("sources", [])
    curated_sources: list[dict[str, object]] = []
    for source_entry in original_sources:
        for spec in plan.documents:
            curated_entry = dict(source_entry)
            curated_entry["document"] = spec.path
            curated_sources.append(curated_entry)

    provenance["sources"] = curated_sources
    provenance["supplemental_sources"] = list(plan.supplemental_sources)
    provenance["images"] = kept_images
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    index["files"] = files
    (map_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    source_path.unlink()


def repair_shangri_la_sections(map_dir: Path) -> None:
    document_path = map_dir / "main_ee.md"
    content = document_path.read_text(encoding="utf-8")
    replacements = {
        "Once done, head back to the minecart": (
            "\n\nAfter knifing all 12 panels, head back to the minecart"
        ),
        "Eight step: Activate the eclipse.": (
            "\n\n## Step 8 - enter the 16-1-3-4 dial code\n\nActivate the eclipse."
        ),
        "Ninth step: Activate the eclipse .": (
            "\n\n## Step 9 - drop and catch the dynamite\n\nActivate the eclipse."
        ),
        "Tenth step: (Finale) Activate the eclipse.": (
            "\n\n## Step 10 - shrink the meteorite and collect the Focusing Stone\n\n"
            "Activate the eclipse."
        ),
    }
    for old, new in replacements.items():
        if old in content:
            content = content.replace(old, new, 1)
    document_path.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split imported Zombies Chronicles Steam guides by topic."
    )
    parser.add_argument(
        "--maps-dir",
        type=Path,
        default=ROOT / "maps",
        help="Knowledge-base maps directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for map_id, plan in PLANS.items():
        map_dir = args.maps_dir / map_id
        if (map_dir / "source_guide.md").is_file():
            curate_map(map_dir, plan)
            print(f"Curated {map_id}: {len(plan.documents)} documents")
        if map_id == "shangri_la":
            repair_shangri_la_sections(map_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
