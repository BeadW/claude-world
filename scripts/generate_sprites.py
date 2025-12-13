#!/usr/bin/env python3
"""Generate placeholder sprites for Claude World."""

from pathlib import Path
import sys

# Add src to path for running directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_world.assets.placeholder_generator import generate_placeholders


def main():
    """Generate all placeholder sprites."""
    output_dir = Path(__file__).parent.parent / "assets" / "sprites"
    print(f"Generating placeholder sprites in {output_dir}")

    generated = generate_placeholders(output_dir)

    if generated:
        print(f"Generated {len(generated)} sprites:")
        for sprite_id, path in generated.items():
            print(f"  - {sprite_id}: {path}")
    else:
        print("No sprites generated (PIL may not be installed)")


if __name__ == "__main__":
    main()
