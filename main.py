"""
Car Benchmarking Agent - FastAPI Server with ADK Runner
"""
import os
import sys
import uuid
import logging
from typing import Optional

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner, InMemorySessionService
from google.genai import types
from typing import Union

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
APP_NAME = "car_benchmarking_agent"

# Initialize session service (shared across requests)
session_service = InMemorySessionService()

# Initialize ADK Runner once at startup
from benchmarking_agent.agent import root_agent

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
    auto_create_session=False  # We manage sessions explicitly in the endpoint
)

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Startup
    logger.info("=" * 60)
    logger.info("CAR BENCHMARKING AGENT - SERVER STARTED")
    logger.info("=" * 60)
    logger.info(f"App: {APP_NAME}  |  Agent: {root_agent.name}  |  Model: {root_agent.model}")
    logger.info("Ready to accept requests!")
    yield
    # Shutdown
    logger.info("Shutting down...")
    try:
        await runner.close()
    except Exception:
        pass


# Create FastAPI app
app = FastAPI(
    title="Car Benchmarking Agent",
    description="AI-powered car comparison with 87 specifications",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/compare")
async def compare_cars(
    query: str = Form(..., description="Your query (e.g., 'Summarize this', 'Compare cars in this with Thar', 'Compare Thar and Swift')"),
    pdf_file: Optional[Union[UploadFile, str]] = File(None, description="Optional PDF with car specifications or reviews"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id", description="User ID from previous response. Pass to continue conversation."),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id", description="Session ID from previous response. Pass to continue conversation."),
):
    """
    Send a query to the car benchmarking agent. Optionally attach a PDF.

    **PDF modes (determined by your query):**
    - `"summarize this"` → returns a document summary
    - `"extract car specs"` → returns specs found in the PDF
    - `"compare cars in this with Mahindra Thar"` → runs full comparison

    **Without PDF:**
    - `"Compare Mahindra Thar, Maruti Swift, Tata Nexon"` → runs full comparison

    **Multi-turn conversation (e.g. CODE car flow):**
    - First response returns `user_id` and `session_id`
    - Pass them in headers `X-User-Id` and `X-Session-Id` to continue the conversation
    """
    try:
        logger.info("=" * 60)
        logger.info("[COMPARE] New request received")
        logger.info(f"[COMPARE] Query: {query[:100]}")
        logger.info(f"[COMPARE] PDF: {pdf_file is not None}")
        logger.info("=" * 60)

        # Get session IDs from headers (secure method)
        user_id = x_user_id
        session_id = x_session_id

        # Session management: create new session or continue existing one
        if user_id and session_id:
            # Try to retrieve existing session to verify it exists
            try:
                existing_session = await session_service.get_session(
                    app_name=APP_NAME,
                    user_id=user_id,
                    session_id=session_id
                )
                logger.info(f"[SESSION] Continuing existing session")
                logger.info(f"[SESSION] user={user_id}  session={session_id}  events={len(existing_session.events) if existing_session else 0}")
            except Exception as e:
                # Session doesn't exist, create new one
                logger.warning(f"[SESSION] Provided session not found, creating new session: {e}")
                user_id = f"user_{uuid.uuid4().hex[:8]}"
                session = await session_service.create_session(
                    app_name=APP_NAME,
                    user_id=user_id
                )
                session_id = session.id
                logger.info(f"[SESSION] Created new session: user={user_id}  session={session_id}")
        else:
            # No session provided, create a new one
            user_id = f"user_{uuid.uuid4().hex[:8]}"
            session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id
            )
            session_id = session.id
            logger.info(f"[SESSION] Created new session: user={user_id}  session={session_id}")

        # Build content parts — PDF first, then user text
        parts = []

        # Treat empty/unset file upload as no file (Swagger sends garbage string when no file selected)
        if not isinstance(pdf_file, UploadFile):
            pdf_file = None

        if pdf_file:
            logger.info(f"[PDF] Processing: {pdf_file.filename}")

            if pdf_file.content_type != "application/pdf":
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type: {pdf_file.content_type}. Only PDF files are supported."
                )

            file_bytes = await pdf_file.read()
            logger.info(f"[PDF] Size: {len(file_bytes)} bytes")

            if len(file_bytes) > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")

            parts.append(types.Part(inline_data=types.Blob(mime_type="application/pdf", data=file_bytes)))
            logger.info("[PDF] Added to content parts")

        # User query — passed exactly as typed, no modifications
        parts.append(types.Part(text=query))
        logger.info(f"[CONTENT] Built {len(parts)} part(s)")

        message = types.Content(role="user", parts=parts)

        # Run agent
        logger.info("[AGENT] Starting execution...")
        full_response = ""
        event_count = 0

        async for event in runner.run_async(
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

        print()  # newline after streamed output
        logger.info(f"[AGENT] Total events: {event_count}")

        if not full_response:
            logger.error("[ERROR] No response from agent")
            raise HTTPException(status_code=500, detail="No response from agent")

        # Log session state after agent run
        try:
            final_session = await session_service.get_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id
            )
            logger.info(f"[SESSION] History now contains {len(final_session.events)} total events")
        except Exception as e:
            logger.warning(f"[SESSION] Could not retrieve final session state: {e}")

        logger.info("[SUCCESS] Returning response")
        return JSONResponse(content={
            "status": "success",
            "query": query,
            "has_pdf": pdf_file is not None and bool(pdf_file.filename),
            "response": full_response,
            "user_id": user_id,
            "session_id": session_id
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
        "service": "Car Benchmarking Agent",
        "version": "2.0.0",
        "endpoints": {"compare": "/compare", "docs": "/docs"}
    }


@app.get("/")
async def root():
    return {
        "service": "Car Benchmarking Agent API",
        "version": "2.0.0",
        "description": "AI-powered car comparison with 87 specifications",
        "endpoints": {
            "compare_cars": "POST /compare",
            "health_check": "GET /health",
            "api_docs": "GET /docs"
        }
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
