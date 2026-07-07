from dotenv import load_dotenv
load_dotenv()
import logging
import os
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import asyncio
import uuid
from app.services.orchestrator.requirement_engine import RequirementEngine
from app.services.test_case_generation.orchestrator import TestCaseEngine
from app.services.test_case_generation.token_budget import estimate_response
from app.services.document_cleaner import clean_document_text
from app.services.file_extractor import extract_text_from_file
from app.shared.ollama_client import warmup
from app.shared.llm.cerebras_provider import CerebrasProvider
from app.shared.llm.groq_provider import GroqProvider
from app.shared.llm.call_llm import (
    request_budget_ctx,
    request_calls_ctx,
    request_id_ctx,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Requirement Intelligence API",
    description="Generate and classify system requirements with batch optimization",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = RequirementEngine()
test_case_engine = TestCaseEngine()


@app.on_event("startup")
async def startup_event():
    """Pre-warm LLM and deduplicator models on startup."""
    try:
        if os.getenv("LLM_PROVIDER", "ollama") != "groq":
            print("Warming up LLM model on startup...")
            start = time.time()
            await warmup()
            elapsed = time.time() - start
            print(f"Warmup complete ({elapsed:.2f}s)")
        else:
            print("Skipping Ollama warmup because LLM_PROVIDER=groq")

        await asyncio.to_thread(engine.semantic_deduplicator.warmup)
        logger.info("Deduplicator warmup complete")
    except Exception as e:
        logger.warning(f"Startup warmup failed (non-blocking): {e}")


class RequirementRequest(BaseModel):
    text: str


class TestCaseEstimateRequest(BaseModel):
    requirements: list[dict]
    project_context: str | None = None
    mode: str = "mvp_fast"


class TestCaseGenerationRequest(BaseModel):
    requirements: list[dict]
    project_context: str | None = None
    mode: str = "mvp_fast"


def _failed_test_case_generation_response(
    mode: str,
    warnings: list[str],
    status: str = "FAILED_SCHEMA_VALIDATION",
    estimated_calls: int = 0,
    estimated_tokens: int = 0,
    calls_used: int = 0,
) -> dict:
    return {
        "status": status,
        "results": [],
        "plans": [],
        "warnings": warnings,
        "budget": {
            "mode": mode,
            "estimated_calls": estimated_calls,
            "estimated_tokens": estimated_tokens,
            "calls_used": calls_used,
        },
    }


@app.get("/health")
async def health():
    return {
        "status": "OK",
        "message": "Requirement Intelligence API is running",
        "optimization": "Batch classification enabled (1 LLM call for all requirements)"
    }


@app.get("/health/groq")
async def groq_health():
    try:
        provider = GroqProvider()
        result = await provider.health_check()
        result["configured_provider"] = os.getenv("LLM_PROVIDER", "ollama")
        return result
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "provider": "groq",
                "status": "ERROR",
                "configured_provider": os.getenv("LLM_PROVIDER", "ollama"),
                "error_type": type(e).__name__,
                "error": str(e),
            },
        )


@app.get("/health/cerebras")
async def cerebras_health():
    if not os.getenv("CEREBRAS_API_KEY"):
        return {
            "provider": "cerebras",
            "status": "NOT_CONFIGURED",
            "configured": False,
            "configured_provider": os.getenv("LLM_PROVIDER", "ollama"),
            "model": os.getenv("CEREBRAS_MODEL", "gpt-oss-120b"),
        }
    try:
        provider = CerebrasProvider()
        result = await provider.health_check()
        result["configured"] = True
        result["configured_provider"] = os.getenv("LLM_PROVIDER", "ollama")
        return result
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "provider": "cerebras",
                "status": "ERROR",
                "configured": True,
                "configured_provider": os.getenv("LLM_PROVIDER", "ollama"),
                "error_type": type(e).__name__,
                "error": str(e),
            },
        )


@app.post("/generate_test_cases/estimate")
async def estimate_test_case_generation(req: TestCaseEstimateRequest):
    try:
        return estimate_response(req.requirements, req.mode)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Estimate error: {str(e)}",
        )


@app.post("/generate_test_cases")
async def generate_test_cases(req: TestCaseGenerationRequest):
    request_id = str(uuid.uuid4())
    request_id_ctx.set(request_id)
    request_calls_ctx.set(0)
    estimate = None

    try:
        estimate = estimate_response(req.requirements, req.mode)
        logger.info(
            f"[REQ {request_id}] TEST_CASE_START | mode={req.mode} | "
            f"allowed={estimate['allowed']}"
        )

        if not estimate["allowed"]:
            return _failed_test_case_generation_response(
                mode=req.mode,
                warnings=estimate["warnings"],
            )

        request_budget_ctx.set({"max_calls": estimate["estimated_calls"]})

        result = await test_case_engine.generate(
            raw_requirements=req.requirements,
            project_context=req.project_context,
            mode=req.mode,
        )

        actual_calls = request_calls_ctx.get()
        if result.budget:
            result.budget.calls_used = actual_calls or result.budget.calls_used

        logger.info(
            f"[REQ {request_id}] TEST_CASE_COMPLETE | "
            f"status={result.status} | calls={result.budget.calls_used}"
        )
        return result.to_dict()

    except Exception as e:
        total_calls = request_calls_ctx.get()
        logger.warning(
            f"[REQ {request_id}] TEST_CASE_FAILED | "
            f"calls={total_calls} | error={e}"
        )
        return _failed_test_case_generation_response(
            mode=req.mode,
            warnings=[f"Test case generation error: {str(e)}"],
            status="PROVIDER_FAILED",
            estimated_calls=estimate.get("estimated_calls", 0)
            if isinstance(estimate, dict)
            else 0,
            estimated_tokens=estimate.get("estimated_tokens", 0)
            if isinstance(estimate, dict)
            else 0,
            calls_used=total_calls,
        )


@app.post("/process")
async def process(req: RequirementRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty")

    request_id = str(uuid.uuid4())
    request_id_ctx.set(request_id)
    request_calls_ctx.set(0)
    request_budget_ctx.set({"max_calls": 12})
    logger.info(f"[REQ {request_id}] START")

    try:
        result = await engine.process(req.text)
        total_calls = request_calls_ctx.get()
        logger.info(f"[REQ {request_id}] COMPLETE | calls={total_calls}")
        return result
    except Exception as e:
        total_calls = request_calls_ctx.get()
        logger.warning(f"[REQ {request_id}] FAILED | calls={total_calls} | error={e}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.post("/process_file")
async def process_file(file: UploadFile = File(...)):
    request_id = str(uuid.uuid4())
    request_id_ctx.set(request_id)
    request_calls_ctx.set(0)
    request_budget_ctx.set({"max_calls": 12})
    logger.info(f"[REQ {request_id}] START")

    try:
        text = await extract_text_from_file(file)
        text = clean_document_text(text)

        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from file"
            )

        result = await engine.process(text)
        total_calls = request_calls_ctx.get()
        logger.info(f"[REQ {request_id}] COMPLETE | calls={total_calls}")
        return result

    except Exception as e:
        total_calls = request_calls_ctx.get()
        logger.warning(f"[REQ {request_id}] FAILED | calls={total_calls} | error={e}")
        raise HTTPException(
            status_code=500,
            detail=f"File processing error: {str(e)}"
        )
