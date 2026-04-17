"""
Vehicle Development Agent - FastAPI Server with ADK Runner
Direct access without authentication
"""
import os
import sys
import uuid
import logging
from typing import Optional, List

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import UploadFile as StarletteUploadFile
from google.adk.runners import Runner, InMemorySessionService

from google.genai import types

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


# Configuration
APP_NAME_VEHICLE_DEVELOPMENT = "vehicle_development_agent"

# Initialize session service
session_service = InMemorySessionService()

# Initialize Vehicle Development agent
from vehicle_development_agent.agent import root_agent as vehicle_development_agent

# Create runner for the agent
vehicle_development_runner = Runner(
    agent=vehicle_development_agent,
    app_name=APP_NAME_VEHICLE_DEVELOPMENT,
    session_service=session_service,
    auto_create_session=False
)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Startup
    logger.info("=" * 80)
    logger.info("VEHICLE DEVELOPMENT AGENT")
    logger.info("=" * 80)
    logger.info(f"Agent: {vehicle_development_agent.name}  |  Model: {vehicle_development_agent.model}")
    logger.info("=" * 80)
    logger.info("Ready to accept requests!")

    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        await vehicle_development_runner.close()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Vehicle Development Agent",
    description="AI-powered vehicle development analysis",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


@app.post("/api/compare")
async def compare_cars(
    query: str = Form(..., description="Your query"),
    pdf_files: List[UploadFile] = File(default=[], description="Optional PDF/Excel/CSV files (max 10 files, 30MB total)"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id", description="User ID from previous response"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id", description="Session ID from previous response"),
):
    """
    Send a query to the Vehicle Development Agent.

    **Multi-File Support (PDF/Excel/CSV):**
    - Upload up to 10 files per request
    - Maximum 10MB per file, 30MB total
    - All files are processed together in context

    **Multi-turn conversation:**
    - First response returns `user_id` and `session_id`
    - Pass them in headers `X-User-Id` and `X-Session-Id` to continue the conversation
    """
    try:
        logger.info("=" * 60)
        logger.info("[COMPARE] New request")
        logger.info(f"[COMPARE] Query: {query[:100]}")
        logger.info(f"[COMPARE] Files: {len(pdf_files)} file(s)")
        logger.info("=" * 60)

        # Get session IDs from headers
        user_id = x_user_id
        session_id = x_session_id

        # Session management
        if user_id and session_id:
            try:
                existing_session = await session_service.get_session(
                    app_name=APP_NAME_VEHICLE_DEVELOPMENT,
                    user_id=user_id,
                    session_id=session_id
                )
                logger.info(f"[SESSION] Continuing existing session")
                logger.info(f"[SESSION] user={user_id}  session={session_id}  events={len(existing_session.events) if existing_session else 0}")
            except Exception as e:
                logger.warning(f"[SESSION] Provided session not found, creating new: {e}")
                user_id = f"user_{uuid.uuid4().hex[:8]}"
                session = await session_service.create_session(
                    app_name=APP_NAME_VEHICLE_DEVELOPMENT,
                    user_id=user_id
                )
                session_id = session.id
                logger.info(f"[SESSION] Created new session: user={user_id}  session={session_id}")
        else:
            user_id = f"user_{uuid.uuid4().hex[:8]}"
            session = await session_service.create_session(
                app_name=APP_NAME_VEHICLE_DEVELOPMENT,
                user_id=user_id
            )
            session_id = session.id
            logger.info(f"[SESSION] Created new session: user={user_id}  session={session_id}")

        # Build content parts
        parts = []
        total_pdf_size = 0
        valid_pdf_count = 0

        valid_pdfs = [
            pdf for pdf in pdf_files
            if isinstance(pdf, (UploadFile, StarletteUploadFile)) and pdf.filename
        ]

        if len(valid_pdfs) > 10:
            raise HTTPException(
                status_code=400,
                detail="Too many files. Maximum 10 files per request."
            )

        SUPPORTED_MIME_TYPES = {
            "application/pdf": "application/pdf",
            "text/csv": "text/csv",
            "application/vnd.ms-excel": "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

        for pdf_file in valid_pdfs:
            logger.info(f"[FILE] Processing: {pdf_file.filename}")

            mime_type = pdf_file.content_type
            filename_lower = pdf_file.filename.lower() if pdf_file.filename else ""

            if mime_type == "application/octet-stream" or mime_type not in SUPPORTED_MIME_TYPES:
                if filename_lower.endswith(".pdf"):
                    mime_type = "application/pdf"
                elif filename_lower.endswith(".csv"):
                    mime_type = "text/csv"
                elif filename_lower.endswith(".xlsx"):
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif filename_lower.endswith(".xls"):
                    mime_type = "application/vnd.ms-excel"

            if mime_type not in SUPPORTED_MIME_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type for {pdf_file.filename}: {pdf_file.content_type}. Supported: PDF, CSV, Excel"
                )

            file_bytes = await pdf_file.read()
            file_size = len(file_bytes)
            total_pdf_size += file_size
            logger.info(f"[FILE] {pdf_file.filename}: {file_size} bytes, type: {mime_type}")

            if file_size > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {pdf_file.filename} too large. Maximum size is 10MB per file."
                )

            if total_pdf_size > 30 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail="Total file size exceeds 30MB limit."
                )

            parts.append(types.Part(inline_data=types.Blob(mime_type=mime_type, data=file_bytes)))
            valid_pdf_count += 1

        if valid_pdf_count > 0:
            logger.info(f"[FILE] Added {valid_pdf_count} file(s), total size: {total_pdf_size} bytes")

        parts.append(types.Part(text=query))
        logger.info(f"[CONTENT] Built {len(parts)} part(s)")

        message = types.Content(role="user", parts=parts)

        # Run the agent
        logger.info("[AGENT] Starting agent execution...")
        full_response = ""
        event_count = 0

        async for event in vehicle_development_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message
        ):
            event_count += 1
            logger.info(f"[AGENT] Event {event_count}: {type(event).__name__}")

            if hasattr(event, 'content') and event.content:
                for part in event.content.parts or []:
                    if hasattr(part, 'text') and part.text:
                        print(part.text, end="", flush=True)

            if event.is_final_response():
                logger.info("[AGENT] Final response received")
                if event.content and event.content.parts:
                    final_text = "".join(
                        p.text for p in event.content.parts if hasattr(p, 'text') and p.text
                    )
                    if final_text:
                        full_response = final_text
                logger.info(f"[AGENT] Response length: {len(full_response)} chars")

        print()
        logger.info(f"[AGENT] Total events: {event_count}")

        if not full_response:
            logger.error("[ERROR] No response from agent")
            raise HTTPException(status_code=500, detail="No response from agent")

        logger.info("[SUCCESS] Returning response")
        return JSONResponse(content={
            "status": "success",
            "agent_type": "Vehicle Development",
            "query": query,
            "pdf_count": valid_pdf_count,
            "response": full_response,
            "user_id": user_id,
            "session_id": session_id,
        })

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"[ERROR] {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Vehicle Development Agent",
        "version": "1.0",
    }


@app.get("/")
async def root():
    return {
        "service": "Vehicle Development Agent API",
        "version": "1.0",
        "status": "running"
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
