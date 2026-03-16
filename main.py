"""
Car Benchmarking Agent - FastAPI Server with ADK Runner and RBAC
Industry-standard JWT authentication with role-based agent routing
"""
import os
import sys
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Header, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import UploadFile as StarletteUploadFile
from google.adk.runners import Runner, InMemorySessionService

from google.genai import types
from typing import Union

# Authentication imports
from auth.models import LoginRequest, LoginResponse, User, UserRole
from auth.jwt_handler import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from auth.database import (
    connect_to_mongodb,
    close_mongodb_connection,
    check_database_health,
    create_conversation,
    get_conversation_by_id,
    get_user_conversations,
    update_conversation,
    delete_conversation,
    delete_old_conversations,
)
from auth.conversation_models import (
    Conversation,
    ConversationMessage,
    ConversationListItem,
)

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
APP_NAME_BENCHMARKING = "car_benchmarking_agent"
APP_NAME_PRODUCT_PLANNING = "product_planning_agent"
APP_NAME_VEHICLE_DEVELOPMENT = "vehicle_development_agent"

# Initialize session service (shared across all agents)
session_service = InMemorySessionService()

# Initialize all three agents based on roles
from benchmarking_agent.agent import root_agent as benchmarking_agent
from product_planning_agent.agent import root_agent as product_planning_agent
from vehicle_development_agent.agent import root_agent as vehicle_development_agent

# Create runners for each agent
benchmarking_runner = Runner(
    agent=benchmarking_agent,
    app_name=APP_NAME_BENCHMARKING,
    session_service=session_service,
    auto_create_session=False
)

product_planning_runner = Runner(
    agent=product_planning_agent,
    app_name=APP_NAME_PRODUCT_PLANNING,
    session_service=session_service,
    auto_create_session=False
)

vehicle_development_runner = Runner(
    agent=vehicle_development_agent,
    app_name=APP_NAME_VEHICLE_DEVELOPMENT,
    session_service=session_service,
    auto_create_session=False
)

# Map roles to their respective runners and app names
ROLE_TO_RUNNER = {
    UserRole.VB: (benchmarking_runner, APP_NAME_BENCHMARKING, "Vehicle Benchmarking"),
    UserRole.PP: (product_planning_runner, APP_NAME_PRODUCT_PLANNING, "Product Planning"),
    UserRole.VD: (vehicle_development_runner, APP_NAME_VEHICLE_DEVELOPMENT, "Vehicle Development"),
}


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Startup
    logger.info("=" * 80)
    logger.info("CAR BENCHMARKING PLATFORM - RBAC WITH MONGODB")
    logger.info("=" * 80)

    # Connect to MongoDB
    try:
        await connect_to_mongodb()
        db_health = await check_database_health()
        logger.info(f"MongoDB: {db_health['status']} | Users: {db_health.get('users_count', 0)}")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        logger.warning("⚠️  Server will start but authentication will fail!")

    logger.info("=" * 80)
    logger.info(f"Benchmarking Agent: {benchmarking_agent.name}  |  Model: {benchmarking_agent.model}")
    logger.info(f"Product Planning Agent: {product_planning_agent.name}  |  Model: {product_planning_agent.model}")
    logger.info(f"Vehicle Development Agent: {vehicle_development_agent.name}  |  Model: {vehicle_development_agent.model}")
    logger.info("=" * 80)
    logger.info("Authentication: JWT-based RBAC with MongoDB")
    logger.info("Roles: VB (Benchmarking) | PP (Product Planning) | VD (Vehicle Development)")
    logger.info("=" * 80)
    logger.info("Ready to accept requests!")

    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        await benchmarking_runner.close()
        await product_planning_runner.close()
        await vehicle_development_runner.close()
        await close_mongodb_connection()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Car Benchmarking Platform with RBAC",
    description="AI-powered car comparison with 87 specifications and role-based access control",
    version="3.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers including Set-Cookie
    max_age=3600,  # Cache preflight requests for 1 hour
)


# ============================================
# AUTHENTICATION ENDPOINTS
# ============================================

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, response: Response):
    """
    Authenticate user and return JWT token

    **Test Credentials:**
    - VB Role: vb@mahindra.com / vb123
    - PP Role: pp@mahindra.com / pp123
    - VD Role: vd@mahindra.com / vd123
    """
    logger.info(f"[AUTH] Login attempt for: {login_data.email}")

    user = await authenticate_user(login_data.email, login_data.password)
    if not user:
        logger.warning(f"[AUTH] Failed login attempt for: {login_data.email}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Set cookie (httpOnly for security)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",  # or "strict" for better security
        secure=False,  # Set to True in production with HTTPS
    )

    logger.info(f"[AUTH] Successful login: {user.email} | Role: {user.role.value}")

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@app.post("/api/auth/logout")
async def logout(response: Response):
    """Logout user by clearing the auth cookie"""
    response.delete_cookie(key="access_token")
    return {"status": "success", "message": "Logged out successfully"}


@app.get("/api/auth/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user"""
    return current_user


# ============================================
# CONVERSATION HISTORY ENDPOINTS
# ============================================

@app.get("/api/conversations", response_model=List[ConversationListItem])
async def get_conversations(current_user: User = Depends(get_current_user)):
    """
    Get user's recent conversations (last 4)
    """
    try:
        conversations = await get_user_conversations(current_user.email, limit=4)

        # Convert to list items
        conversation_list = [
            ConversationListItem(
                conversation_id=conv["conversation_id"],
                title=conv["title"],
                created_at=conv["created_at"],
                updated_at=conv["updated_at"],
                message_count=len(conv.get("messages", []))
            )
            for conv in conversations
        ]

        return conversation_list

    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        raise HTTPException(status_code=500, detail="Error fetching conversations")


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific conversation by ID
    """
    try:
        conversation = await get_conversation_by_id(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Verify user owns this conversation
        if conversation["user_email"] != current_user.email:
            raise HTTPException(status_code=403, detail="Access denied")

        return Conversation(**conversation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation: {e}")
        raise HTTPException(status_code=500, detail="Error fetching conversation")


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a conversation
    """
    try:
        conversation = await get_conversation_by_id(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Verify user owns this conversation
        if conversation["user_email"] != current_user.email:
            raise HTTPException(status_code=403, detail="Access denied")

        success = await delete_conversation(conversation_id)

        if success:
            return {"status": "success", "message": "Conversation deleted"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete conversation")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail="Error deleting conversation")


# ============================================
# PROTECTED AGENT ENDPOINTS
# ============================================

@app.post("/api/compare")
async def compare_cars(
    query: str = Form(..., description="Your query (e.g., 'Summarize this', 'Compare cars in this with Thar', 'Compare Thar and Swift')"),
    pdf_files: List[UploadFile] = File(default=[], description="Optional PDFs with car specifications or reviews (max 10 files, 30MB total)"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id", description="User ID from previous response. Pass to continue conversation."),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id", description="Session ID from previous response. Pass to continue conversation."),
    x_conversation_id: Optional[str] = Header(None, alias="X-Conversation-Id", description="Conversation ID to continue existing conversation."),
    current_user: User = Depends(get_current_user),  # JWT authentication required
):
    """
    Send a query to the appropriate agent based on user role.

    **Role-based Agent Routing:**
    - VB Role → Vehicle Benchmarking Agent
    - PP Role → Product Planning Agent
    - VD Role → Vehicle Development Agent

    **Multi-PDF Support:**
    - Upload up to 10 PDF files per request
    - Maximum 10MB per file, 30MB total
    - All PDFs are processed together in context

    **PDF modes (determined by your query):**
    - `"summarize these"` → returns document summaries
    - `"extract car specs"` → returns specs found in the PDFs
    - `"compare cars in these with Mahindra Thar"` → runs full comparison

    **Without PDF:**
    - `"Compare Mahindra Thar, Maruti Swift, Tata Nexon"` → runs full comparison

    **Multi-turn conversation (e.g. CODE car flow):**
    - First response returns `user_id` and `session_id`
    - Pass them in headers `X-User-Id` and `X-Session-Id` to continue the conversation
    """
    try:
        # Get the appropriate runner based on user role
        runner, app_name, agent_type = ROLE_TO_RUNNER[current_user.role]

        logger.info("=" * 60)
        logger.info("[COMPARE] New authenticated request")
        logger.info(f"[AUTH] User: {current_user.email} | Role: {current_user.role.value} | Agent: {agent_type}")
        logger.info(f"[COMPARE] Query: {query[:100]}")
        logger.info(f"[COMPARE] PDFs: {len(pdf_files)} file(s)")
        logger.info("=" * 60)

        # Get session IDs from headers (secure method)
        user_id = x_user_id
        session_id = x_session_id

        # Session management: create new session or continue existing one
        if user_id and session_id:
            # Try to retrieve existing session to verify it exists
            try:
                existing_session = await session_service.get_session(
                    app_name=app_name,
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
                    app_name=app_name,
                    user_id=user_id
                )
                session_id = session.id
                logger.info(f"[SESSION] Created new session: user={user_id}  session={session_id}")
        else:
            # No session provided, create a new one
            user_id = f"user_{uuid.uuid4().hex[:8]}"
            session = await session_service.create_session(
                app_name=app_name,
                user_id=user_id
            )
            session_id = session.id
            logger.info(f"[SESSION] Created new session: user={user_id}  session={session_id}")

        # Build content parts — PDFs first, then user text
        parts = []
        total_pdf_size = 0
        valid_pdf_count = 0

        # Filter out invalid uploads (Swagger sends garbage string when no file selected)
        valid_pdfs = [
            pdf for pdf in pdf_files
            if isinstance(pdf, (UploadFile, StarletteUploadFile)) and pdf.filename
        ]

        # Validate limits
        if len(valid_pdfs) > 10:
            raise HTTPException(
                status_code=400,
                detail="Too many files. Maximum 10 PDFs per request."
            )

        # Process each PDF
        for pdf_file in valid_pdfs:
            logger.info(f"[PDF] Processing: {pdf_file.filename}")

            if pdf_file.content_type != "application/pdf":
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type for {pdf_file.filename}: {pdf_file.content_type}. Only PDF files are supported."
                )

            file_bytes = await pdf_file.read()
            file_size = len(file_bytes)
            total_pdf_size += file_size
            logger.info(f"[PDF] {pdf_file.filename}: {file_size} bytes")

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

            parts.append(types.Part(inline_data=types.Blob(mime_type="application/pdf", data=file_bytes)))
            valid_pdf_count += 1

        if valid_pdf_count > 0:
            logger.info(f"[PDF] Added {valid_pdf_count} PDF(s) to content parts, total size: {total_pdf_size} bytes")

        # User query — passed exactly as typed, no modifications
        parts.append(types.Part(text=query))
        logger.info(f"[CONTENT] Built {len(parts)} part(s)")

        message = types.Content(role="user", parts=parts)

        # Run the appropriate agent based on user role
        logger.info(f"[AGENT] Starting {agent_type} agent execution...")
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
                app_name=app_name,
                user_id=user_id,
                session_id=session_id
            )
            logger.info(f"[SESSION] History now contains {len(final_session.events)} total events")
        except Exception as e:
            logger.warning(f"[SESSION] Could not retrieve final session state: {e}")

        # ============================================
        # SAVE CONVERSATION TO MONGODB
        # ============================================
        conversation_id = x_conversation_id
        current_time = datetime.utcnow()

        # Create message objects
        user_message = {
            "role": "user",
            "content": query,
            "timestamp": current_time,
        }

        assistant_message = {
            "role": "assistant",
            "content": full_response,
            "timestamp": current_time,
        }

        # Extract metadata from response
        import re
        report_url_match = re.search(r'https://storage\.googleapis\.com/[^\s]+', full_response)
        if report_url_match:
            assistant_message["report_url"] = report_url_match.group(0)

        cars_match = re.search(r'Compared:\s*(.+?)(?:\n|$)', full_response)
        if cars_match:
            assistant_message["cars_compared"] = cars_match.group(1).strip()

        time_match = re.search(r'Time:\s*([\d.]+)\s*seconds?', full_response)
        if time_match:
            assistant_message["time_taken"] = f"{time_match.group(1)}s"

        try:
            if conversation_id:
                # Update existing conversation
                existing_conv = await get_conversation_by_id(conversation_id)
                if existing_conv and existing_conv["user_email"] == current_user.email:
                    messages = existing_conv.get("messages", [])
                    messages.append(user_message)
                    messages.append(assistant_message)

                    await update_conversation(conversation_id, {
                        "messages": messages,
                        "updated_at": current_time,
                    })
                    logger.info(f"[CONVERSATION] Updated conversation: {conversation_id}")
                else:
                    conversation_id = None  # Create new if not found or access denied

            if not conversation_id:
                # Create new conversation
                conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

                # Generate title from first message (truncate to 50 chars)
                title = query[:50] + "..." if len(query) > 50 else query

                conversation_data = {
                    "conversation_id": conversation_id,
                    "user_email": current_user.email,
                    "title": title,
                    "messages": [user_message, assistant_message],
                    "created_at": current_time,
                    "updated_at": current_time,
                    "session_id": session_id,
                    "user_id": user_id,
                }

                await create_conversation(conversation_data)
                logger.info(f"[CONVERSATION] Created new conversation: {conversation_id}")

                # Delete old conversations beyond limit of 4
                await delete_old_conversations(current_user.email, keep_count=4)

        except Exception as e:
            logger.error(f"[CONVERSATION] Error saving conversation: {e}")
            # Don't fail the request if conversation save fails

        logger.info("[SUCCESS] Returning response")
        return JSONResponse(content={
            "status": "success",
            "agent_type": agent_type,
            "user_role": current_user.role.value,
            "query": query,
            "pdf_count": valid_pdf_count,
            "response": full_response,
            "user_id": user_id,
            "session_id": session_id,
            "conversation_id": conversation_id
        })

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"[ERROR] {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


# ============================================
# PUBLIC ENDPOINTS
# ============================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Car Benchmarking Platform with RBAC",
        "version": "3.1",
    }


@app.get("/")
async def root():
    return {
        "service": "Car Benchmarking Platform API",
        "version": "3.1",
        "status": "running"
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
