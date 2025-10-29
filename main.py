"""
Santa API - Backend service for managing Tavus-powered Santa video calls
Handles: Call initialization, personalization, conversation arcs, analytics
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
import httpx
import os
import yaml
import random
from datetime import datetime, timedelta
import json

app = FastAPI(
    title="Santa API",
    description="Backend service for personalized Santa video calls",
    version="1.0.0"
)

# CORS - Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
TAVUS_API_KEY = os.getenv("TAVUS_API_KEY")
TAVUS_PERSONA_ID = os.getenv("TAVUS_PERSONA_ID")
TAVUS_BASE_URL = "https://tavusapi.com/v2"

# Debug: Print environment variable status on startup
print("=" * 60)
print("ENVIRONMENT VARIABLE DEBUG:")
print(f"TAVUS_API_KEY present: {bool(TAVUS_API_KEY)}")
print(f"TAVUS_API_KEY length: {len(TAVUS_API_KEY) if TAVUS_API_KEY else 0}")
print(f"TAVUS_PERSONA_ID present: {bool(TAVUS_PERSONA_ID)}")
print(f"TAVUS_PERSONA_ID length: {len(TAVUS_PERSONA_ID) if TAVUS_PERSONA_ID else 0}")
print("=" * 60)

# Load conversation arcs from YAML
with open("conversation-arcs.yaml", "r") as f:
    CONVERSATION_ARCS = yaml.safe_load(f)

# In-memory analytics storage (replace with database in production)
analytics_store = []

# ==================== Request/Response Models ====================

class StartCallRequest(BaseModel):
    child_name: str = Field(..., min_length=1, max_length=50, description="Child's first name")
    child_age: int = Field(..., ge=2, le=12, description="Child's age (2-12)")
    call_duration: str = Field(..., description="Call duration: '5min' or '10min'")
    parent_email: Optional[str] = Field(None, description="Parent's email for analytics")

    @validator('call_duration')
    def validate_duration(cls, v):
        if v not in ['5min', '10min']:
            raise ValueError("call_duration must be '5min' or '10min'")
        return v

class StartCallResponse(BaseModel):
    conversation_id: str
    conversation_url: str
    expires_at: str
    call_metadata: Dict
    estimated_end_time: str

class CallCompletionRequest(BaseModel):
    conversation_id: str
    actual_duration_seconds: int
    parent_rating: Optional[int] = Field(None, ge=1, le=5)
    parent_feedback: Optional[str] = None
    child_enjoyed: Optional[bool] = None

class AnalyticsResponse(BaseModel):
    total_calls: int
    calls_today: int
    average_duration_seconds: float
    average_rating: float
    calls_by_duration: Dict[str, int]
    calls_by_age: Dict[str, int]

# ==================== Helper Functions ====================

def load_conversation_arc(duration: str, age: int) -> Dict:
    """Load conversation arc from YAML config"""
    arc_data = CONVERSATION_ARCS['arcs'][duration].copy()

    # Add age-specific adaptations
    if age <= 4:
        arc_data['age_adaptation'] = CONVERSATION_ARCS['age_adaptations']['ages_2_4']
    elif age <= 8:
        arc_data['age_adaptation'] = CONVERSATION_ARCS['age_adaptations']['ages_5_8']
    else:
        arc_data['age_adaptation'] = CONVERSATION_ARCS['age_adaptations']['ages_9_12']

    # Add timing guidelines
    arc_data['timing'] = CONVERSATION_ARCS['timing_guidelines'][duration]

    return arc_data

def generate_greeting(child_name: str, child_age: int) -> str:
    """Generate personalized greeting based on age"""
    if child_age <= 4:
        templates = CONVERSATION_ARCS['greeting_templates']['ages_2_4']
    elif child_age <= 8:
        templates = CONVERSATION_ARCS['greeting_templates']['ages_5_8']
    else:
        templates = CONVERSATION_ARCS['greeting_templates']['ages_9_12']

    # Pick random template and format with child's name
    template = random.choice(templates)

    # Determine gender-neutral term
    child_term = "child"

    return template.format(child_name=child_name, child=child_term)

def create_system_prompt(child_name: str, child_age: int, duration: str, greeting: str, arc: Dict) -> str:
    """Create enhanced system prompt with conversation context"""

    prompt = f"""
PERSONALIZED CONVERSATION CONTEXT:

Child Information:
- Name: {child_name}
- Age: {child_age} years old
- Call Duration: {duration} ({arc['total_duration_seconds']} seconds)
- Language Level: {arc['age_adaptation']['language_level']}

MANDATORY GREETING:
Start the conversation with: "{greeting}"

CONVERSATION STRUCTURE:
You must follow this {duration} arc with {len(arc['phases'])} phases:

"""

    # Add each phase details
    for i, phase in enumerate(arc['phases'], 1):
        prompt += f"""
Phase {i}: {phase['name'].replace('_', ' ').title()} ({phase['duration_seconds']}s - {phase['percentage']}%)
Goals:
{chr(10).join([f'  - {goal}' for goal in phase['goals']])}

Guidelines:
{chr(10).join([f'  - {guideline}' for guideline in phase['santa_guidelines']])}
"""

        # Add suggested questions if available
        if 'suggested_questions' in phase:
            prompt += f"\nSuggested Questions:\n"
            prompt += chr(10).join([f'  - {q}' for q in phase['suggested_questions']])
            prompt += "\n"

    # Add age-specific adaptations
    prompt += f"""

AGE-SPECIFIC ADAPTATIONS (Age {child_age}):
- Response Length: {arc['age_adaptation']['response_length']}
- Sentence Complexity: {arc['age_adaptation']['sentence_complexity']}
- Energy Level: {arc['age_adaptation']['energy']}
- Attention Span: {arc['age_adaptation']['attention_span']}

TIMING GUIDELINES:
- Average response: {arc['timing']['average_response_length_seconds']} seconds
- Max response: {arc['timing']['max_response_length_seconds']} seconds
- Pause between responses: {arc['timing']['pause_between_responses_seconds']} seconds

CONVERSATION RULES:
1. Use {child_name}'s name naturally 2-3 times per minute
2. Keep responses within time limits for your age group
3. Listen actively - reference what the child says
4. Never promise specific gifts - use "I'll see what I can do" or "I'll talk to my elves"
5. Stay in character as Santa Claus at all times
6. If child shows objects, acknowledge and comment on them
7. Keep the magic of Christmas alive
8. Be warm, encouraging, and kind
9. Follow the phase structure but allow natural conversation flow
10. If running long, gracefully transition to closing phase

QUALITY INDICATORS:
- Child is engaged and responding
- Conversation feels natural, not scripted
- Child seems comfortable and happy
- Name usage feels natural, not forced
- Transitions between phases are smooth

Remember: You are Santa Claus. Be magical, kind, and create a memorable experience for {child_name}!
"""

    return prompt

def track_call_started(call_data: Dict):
    """Track call initiation for analytics"""
    analytics_store.append({
        'event': 'call_started',
        'timestamp': datetime.utcnow().isoformat(),
        'conversation_id': call_data['conversation_id'],
        'child_age': call_data['child_age'],
        'call_duration': call_data['call_duration'],
        'parent_email': call_data.get('parent_email')
    })

def track_call_completed(completion_data: Dict):
    """Track call completion for analytics"""
    analytics_store.append({
        'event': 'call_completed',
        'timestamp': datetime.utcnow().isoformat(),
        **completion_data
    })

# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """API information"""
    return {
        "service": "santa-api",
        "version": "1.0.0",
        "description": "Backend service for personalized Santa video calls",
        "endpoints": {
            "POST /api/santa/start-call": "Initialize a new Santa call",
            "POST /api/santa/complete-call": "Record call completion and analytics",
            "GET /api/santa/analytics": "Get call analytics",
            "GET /api/health": "Health check"
        }
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    # Verify configuration
    config_status = {
        "tavus_api_key_set": bool(TAVUS_API_KEY),
        "tavus_persona_id_set": bool(TAVUS_PERSONA_ID),
        "conversation_arcs_loaded": bool(CONVERSATION_ARCS),
        "arcs_available": list(CONVERSATION_ARCS.get('arcs', {}).keys())
    }

    # Check if Tavus API is reachable (simple ping)
    tavus_reachable = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TAVUS_BASE_URL}/personas",
                headers={"x-api-key": TAVUS_API_KEY},
                timeout=5.0
            )
            tavus_reachable = response.status_code in [200, 401]  # 401 means API is up, auth issue
    except:
        pass

    return {
        "status": "healthy",
        "service": "santa-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "configuration": config_status,
        "tavus_api_reachable": tavus_reachable,
        "total_calls_tracked": len([x for x in analytics_store if x['event'] == 'call_started'])
    }

@app.post("/api/santa/start-call", response_model=StartCallResponse)
async def start_santa_call(
    request: StartCallRequest,
    background_tasks: BackgroundTasks
):
    """
    Initialize a personalized Santa video call

    This endpoint:
    1. Validates input parameters
    2. Generates personalized greeting
    3. Loads appropriate conversation arc
    4. Creates enhanced system prompt
    5. Calls Tavus API to create conversation
    6. Returns video URL for frontend embedding
    7. Tracks call initiation for analytics
    """

    # Validate Tavus credentials
    if not TAVUS_API_KEY or not TAVUS_PERSONA_ID:
        raise HTTPException(
            status_code=500,
            detail="Tavus API credentials not configured. Please set TAVUS_API_KEY and TAVUS_PERSONA_ID environment variables."
        )

    # Generate personalized content
    greeting = generate_greeting(request.child_name, request.child_age)
    conversation_arc = load_conversation_arc(request.call_duration, request.child_age)
    system_prompt = create_system_prompt(
        request.child_name,
        request.child_age,
        request.call_duration,
        greeting,
        conversation_arc
    )

    # Prepare Tavus API request
    max_duration = 300 if request.call_duration == "5min" else 600

    tavus_request = {
        "persona_id": TAVUS_PERSONA_ID,
        "conversation_name": f"Santa call with {request.child_name}",
        "conversational_context": system_prompt,
        "properties": {
            "max_call_duration": max_duration,
            "enable_recording": False,  # Set to True if you want recordings
            "participant_left_timeout": 60,
        },
        "custom_metadata": {
            "child_name": request.child_name,
            "child_age": request.child_age,
            "call_duration": request.call_duration,
            "parent_email": request.parent_email
        }
    }

    # Call Tavus API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TAVUS_BASE_URL}/conversations",
                headers={
                    "x-api-key": TAVUS_API_KEY,
                    "Content-Type": "application/json"
                },
                json=tavus_request,
                timeout=30.0
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Tavus API error: {response.text}"
                )

            tavus_data = response.json()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Timeout connecting to Tavus API. Please try again."
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Error connecting to Tavus API: {str(e)}"
        )

    # Calculate estimated end time
    estimated_end = datetime.utcnow() + timedelta(seconds=max_duration)

    # Prepare response
    response_data = StartCallResponse(
        conversation_id=tavus_data["conversation_id"],
        conversation_url=tavus_data["conversation_url"],
        expires_at=tavus_data.get("expires_at", estimated_end.isoformat()),
        call_metadata={
            "child_name": request.child_name,
            "child_age": request.child_age,
            "call_duration": request.call_duration,
            "greeting": greeting,
            "arc_name": conversation_arc['name'],
            "phases": len(conversation_arc['phases'])
        },
        estimated_end_time=estimated_end.isoformat()
    )

    # Track analytics in background
    background_tasks.add_task(
        track_call_started,
        {
            "conversation_id": tavus_data["conversation_id"],
            "child_age": request.child_age,
            "call_duration": request.call_duration,
            "parent_email": request.parent_email
        }
    )

    return response_data

@app.post("/api/santa/complete-call")
async def complete_call(
    request: CallCompletionRequest,
    background_tasks: BackgroundTasks
):
    """
    Record call completion and collect analytics

    Called by frontend after call ends to track:
    - Actual call duration
    - Parent rating (1-5 stars)
    - Parent feedback
    - Whether child enjoyed the call
    """

    # Track completion in background
    background_tasks.add_task(
        track_call_completed,
        {
            "conversation_id": request.conversation_id,
            "actual_duration_seconds": request.actual_duration_seconds,
            "parent_rating": request.parent_rating,
            "parent_feedback": request.parent_feedback,
            "child_enjoyed": request.child_enjoyed
        }
    )

    return {
        "status": "success",
        "message": "Call completion recorded",
        "conversation_id": request.conversation_id
    }

@app.get("/api/santa/analytics", response_model=AnalyticsResponse)
async def get_analytics():
    """
    Get aggregated analytics for all Santa calls

    Returns:
    - Total calls
    - Calls today
    - Average duration
    - Average rating
    - Breakdown by duration (5min vs 10min)
    - Breakdown by age group
    """

    if not analytics_store:
        return AnalyticsResponse(
            total_calls=0,
            calls_today=0,
            average_duration_seconds=0.0,
            average_rating=0.0,
            calls_by_duration={},
            calls_by_age={}
        )

    # Filter events
    started_calls = [x for x in analytics_store if x['event'] == 'call_started']
    completed_calls = [x for x in analytics_store if x['event'] == 'call_completed']

    # Total calls
    total_calls = len(started_calls)

    # Calls today
    today = datetime.utcnow().date()
    calls_today = len([
        x for x in started_calls
        if datetime.fromisoformat(x['timestamp']).date() == today
    ])

    # Average duration
    if completed_calls:
        avg_duration = sum(x['actual_duration_seconds'] for x in completed_calls) / len(completed_calls)
    else:
        avg_duration = 0.0

    # Average rating
    ratings = [x['parent_rating'] for x in completed_calls if x.get('parent_rating')]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    # Calls by duration
    calls_by_duration = {}
    for call in started_calls:
        duration = call['call_duration']
        calls_by_duration[duration] = calls_by_duration.get(duration, 0) + 1

    # Calls by age
    calls_by_age = {}
    for call in started_calls:
        age = str(call['child_age'])
        calls_by_age[age] = calls_by_age.get(age, 0) + 1

    return AnalyticsResponse(
        total_calls=total_calls,
        calls_today=calls_today,
        average_duration_seconds=round(avg_duration, 1),
        average_rating=round(avg_rating, 2),
        calls_by_duration=calls_by_duration,
        calls_by_age=calls_by_age
    )

@app.get("/api/santa/arcs/{duration}")
async def get_conversation_arc(duration: str):
    """
    Get conversation arc details for a specific duration

    Useful for debugging or showing parents what to expect
    """
    if duration not in ['5min', '10min']:
        raise HTTPException(400, "Duration must be '5min' or '10min'")

    arc = CONVERSATION_ARCS['arcs'].get(duration)
    if not arc:
        raise HTTPException(404, "Arc not found")

    return {
        "duration": duration,
        "arc": arc,
        "timing_guidelines": CONVERSATION_ARCS['timing_guidelines'][duration]
    }

# ==================== Error Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom error response format"""
    return {
        "error": True,
        "status_code": exc.status_code,
        "message": exc.detail,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
