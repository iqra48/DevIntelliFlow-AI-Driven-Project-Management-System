"""
Interactive Full System Test
User Input → Generation → Classification
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.generation_service import generate_requirements
from app.domain.classification_pipeline import ClassificationPipeline
from app.services.batch_classifier import classify_requirements_batch
from app.shared.ollama_client import warmup


async def main():
    import os
    pipeline = ClassificationPipeline()
    
    # Show optimization info
    print("\n" + "="*90)
    print("REQUIREMENT SYSTEM - LIVE TEST")
    print("="*90)
    print("\n⚙️  OPTIMIZATION STATUS:")
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")
    threads = os.getenv("OLLAMA_NUM_THREAD", "auto")
    predict = os.getenv("OLLAMA_NUM_PREDICT", "512")
    print(f"   Model: {model}")
    print(f"   CPU Threads: {threads}")
    print(f"   Max Tokens: {predict}")
    print()
    
    # Warmup Ollama to reduce first-call latency
    try:
        print("🔁 Warming up LLM (this may take a moment)...")
        w = await warmup()
        print(f"✅ Warmup completed in {w:.2f}s\n")
    except Exception:
        print("⚠️ Warmup failed or skipped\n")
    
    # Show optimization hints
    print("💡 PERFORMANCE TIPS:")
    print("   To speed up further on CPU:")
    print("     • Set CPU threads: $env:OLLAMA_NUM_THREAD = '8' (use your core count)")
    print("     • Use quantized model: $env:OLLAMA_MODEL = 'llama3.1:8b-instruct-q4_K_M'")
    print("   (Run 'ollama pull llama3.1:8b-instruct-q4_K_M' first to install Q4 version)")
    print()
    
    print("\n" + "="*90)
    print("REQUIREMENT SYSTEM - LIVE TEST")
    print("="*90)
    print("\nEnter your requirement description and watch the system work!\n")
    
    while True:
        print("-" * 90)
        user_input = input("\n📝 Enter requirement description (or 'quit' to exit):\n> ").strip()
        
        if not user_input or user_input.lower() == 'quit':
            print("\n✅ Goodbye!\n")
            break
        
        print("\n" + "="*90)
        print("PROCESSING")
        print("="*90)
        
        try:
            # PHASE 1: GENERATE
            print("\n📥 INPUT:")
            print(f"   {user_input}\n")
            
            print("🔧 GENERATING REQUIREMENTS...")
            t0 = time.perf_counter()
            generated = await generate_requirements(user_input)
            gen_elapsed = time.perf_counter() - t0
            print(f"   → Generation took {gen_elapsed:.2f}s")
            
            if not generated:
                print("❌ No requirements generated\n")
                continue
            
            print(f"✅ Generated {len(generated)} requirement(s):\n")
            for i, req in enumerate(generated, 1):
                print(f"   {i}. {req}")
            
            # PHASE 2: CLASSIFY (batch mode - single LLM call for all)
            print("\n🔄 BATCH CLASSIFYING (1 LLM call for all)...\n")

            fr_count = 0
            nfr_count = 0
            mixed_count = 0
            results = []

            classification_start = time.perf_counter()
            
            # Single batch call to classify all requirements at once
            batch_classifications = await classify_requirements_batch(generated)
            
            for idx, req in enumerate(generated, 1):
                req_type = batch_classifications.get(req, "FR")  # default to FR
                print(f"   [{idx}/{len(generated)}] {req[:70]}...", end=" ")
                
                if req_type == "FR":
                    fr_count += 1
                    print("🟦 FR")
                elif req_type == "NFR":
                    nfr_count += 1
                    print("🟪 NFR")
                else:
                    mixed_count += 1
                    print("🟩 MIXED")
                
                results.append({
                    "req": req,
                    "type": req_type,
                    "simple": True  # Flagged as coming from batch classifier
                })
            
            classification_elapsed = time.perf_counter() - classification_start
            # RESULTS
            print("\n" + "="*90)
            print("RESULTS")
            print("="*90)
            print(f"\nTotal: {len(results)} | 🟦 FR: {fr_count} | 🟪 NFR: {nfr_count} | 🟩 MIXED: {mixed_count}\n")
            print(f"Classification total time: {classification_elapsed:.2f}s")
            
            # DETAILS
            for i, r in enumerate(results, 1):
                print(f"\n{i}. [{r['type']}] {r['req']}")
                
                # Only show audit details if available (from full pipeline)
                if 'audit' in r:
                    audit = r['audit']
                    if audit.semantic_units:
                        print(f"   Components:")
                        for unit in audit.semantic_units[:2]:
                            print(f"     • {unit}")
                    
                    if audit.explainability:
                        exp = audit.explainability[:100] + "..." if len(audit.explainability) > 100 else audit.explainability
                        print(f"   Reason: {exp}")
                else:
                    # Just show the classification (from batch classifier)
                    print(f"   (Batch classified as {r['type']})")
            
            print("\n" + "="*90)
        
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Stopped by user\n")

