"""PyInstaller entry point (the same script is built twice: windowed ClaudePet.exe, console claude-pet-cli.exe)."""
import sys

from claude_pet.cli import main

if __name__ == "__main__":
    sys.exit(main())
