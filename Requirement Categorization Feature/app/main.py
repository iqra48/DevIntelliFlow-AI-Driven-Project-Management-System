from dotenv import load_dotenv
load_dotenv()
import logging
import os
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import uuid
from app.services.orchestrator.requirement_engine import RequirementEngine
from app.services.documents import clean_document_text, extract_text_from_file
from app.infrastructure.llm.groq_provider import GroqProvider
from app.infrastructure.llm.call_llm import (
    request_budget_ctx,
    request_calls_ctx,
    request_id_ctx,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Requirement Categorization Feature",
    description="Categorize system requirements as functional or non-functional with batch optimization",
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


@app.on_event("startup")
async def startup_event():
    """Pre-warm non-LLM supporting models on startup."""
    try:
        print("Using Groq as the only LLM provider")

        await asyncio.to_thread(engine.semantic_deduplicator.warmup)
        logger.info("Deduplicator warmup complete")
    except Exception as e:
        logger.warning(f"Startup warmup failed (non-blocking): {e}")


class RequirementRequest(BaseModel):
    text: str


@app.get("/health")
async def health():
    return {
        "status": "OK",
        "message": "Requirement Categorization Feature is running",
        "optimization": "Batch classification enabled (1 LLM call for all requirements)"
    }


@app.get("/health/groq")
async def groq_health():
    try:
        provider = GroqProvider()
        result = await provider.health_check()
        result["configured_provider"] = os.getenv("LLM_PROVIDER", "groq")
        return result
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "provider": "groq",
                "status": "ERROR",
                "configured_provider": os.getenv("LLM_PROVIDER", "groq"),
                "error_type": type(e).__name__,
                "error": str(e),
            },
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
