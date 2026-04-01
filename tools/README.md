# /tools — Modular Tool Registry

This directory contains standalone, reusable Python modules for the Text2Beluga factory pipeline.

## Available Tools

| Module | Purpose |
|---|---|
| `audio_fetcher.py` | MyInstants scraper — downloads missing meme sounds |
| `schema_validator.py` | Validates scenario.json against the interaction engine schema |

## Architecture

Each tool is a standalone Python module that can be:
1. Imported by `main_factory.py` as part of the pipeline
2. Run independently via CLI for debugging

## Adding New Tools

Create a new `.py` file in this directory. It will be auto-discovered by `main_factory.py`'s tool registry.
