"""Interactive CLI for local requirement generation and classification."""

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.requirements.batch_classifier import classify_requirements_batch
from app.services.requirements.generation_service import generate_requirements


async def main() -> None:
    print("\n" + "=" * 80)
    print("REQUIREMENT SYSTEM - LOCAL CLI")
    print("=" * 80)
    print(f"Provider: {os.getenv('LLM_PROVIDER', 'groq')}")
    print(f"Groq model: {os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}")
    print("\nEnter a requirement description, or type 'quit' to exit.\n")

    while True:
        user_input = input("> ").strip()

        if not user_input or user_input.lower() == "quit":
            print("Goodbye.")
            break

        try:
            started = time.perf_counter()
            generated = await generate_requirements(user_input)
            generation_elapsed = time.perf_counter() - started

            if not generated:
                print("No requirements generated.\n")
                continue

            print(f"\nGenerated {len(generated)} requirement(s) in {generation_elapsed:.2f}s:")
            for index, requirement in enumerate(generated, 1):
                print(f"{index}. {requirement}")

            started = time.perf_counter()
            classifications = await classify_requirements_batch(generated)
            classification_elapsed = time.perf_counter() - started

            print(f"\nClassified in {classification_elapsed:.2f}s:")
            for index, requirement in enumerate(generated, 1):
                requirement_type = classifications.get(requirement, {}).get("type", "FR")
                print(f"{index}. [{requirement_type}] {requirement}")

            print()
        except Exception as exc:
            print(f"Error: {exc}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
