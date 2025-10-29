# Santa API - Tavus Integration Backend

Backend service for managing personalized Santa video calls via Tavus.

## Features

✅ **Personalized Call Initialization**
- Accept child name, age, and preferred duration (5min or 10min)
- Generate age-appropriate greetings
- Load conversation arcs from YAML configuration
- Create enhanced system prompts with context
- Call Tavus API to start video conversation

✅ **Configuration-Based Conversation Arcs**
- 5-minute and 10-minute conversation structures
- Age-specific language adaptations (2-4, 5-8, 9-12)
- Phase-based conversation flow
- Timing guidelines for natural pacing
- Quality metrics and success indicators

✅ **Post-Call Analytics**
- Track call initiations
- Record call completions
- Collect parent ratings (1-5 stars)
- Gather parent feedback
- Aggregate statistics (total calls, average duration, ratings)
- Breakdown by duration and age

## API Endpoints

### `POST /api/santa/start-call`
Initialize a new Santa call

**Request:**
```json
{
  "child_name": "Emma",
  "child_age": 7,
  "call_duration": "5min",
  "parent_email": "parent@example.com"
}
```

**Response:**
```json
{
  "conversation_id": "conv_123abc",
  "conversation_url": "https://tavus.io/c/conv_123abc",
  "expires_at": "2025-10-29T10:00:00Z",
  "call_metadata": {
    "child_name": "Emma",
    "child_age": 7,
    "call_duration": "5min",
    "greeting": "Ho ho ho! Emma! I've been so excited to talk to you!",
    "arc_name": "Quick Chat with Santa",
    "phases": 4
  },
  "estimated_end_time": "2025-10-29T09:05:00Z"
}
```

### `POST /api/santa/complete-call`
Record call completion and analytics

**Request:**
```json
{
  "conversation_id": "conv_123abc",
  "actual_duration_seconds": 285,
  "parent_rating": 5,
  "parent_feedback": "Amazing experience!",
  "child_enjoyed": true
}
```

### `GET /api/santa/analytics`
Get aggregated analytics

**Response:**
```json
{
  "total_calls": 150,
  "calls_today": 12,
  "average_duration_seconds": 295.5,
  "average_rating": 4.8,
  "calls_by_duration": {
    "5min": 90,
    "10min": 60
  },
  "calls_by_age": {
    "4": 20,
    "5": 25,
    "6": 30,
    "7": 28,
    "8": 22,
    "9": 15,
    "10": 10
  }
}
```

### `GET /api/santa/arcs/{duration}`
Get conversation arc details

### `GET /api/health`
Health check and configuration status

## Configuration

### Environment Variables

Required:
- `TAVUS_API_KEY` - Your Tavus API key
- `TAVUS_PERSONA_ID` - Your Santa persona ID

### Conversation Arcs

Edit `conversation-arcs.yaml` to customize:
- Conversation phases and timing
- Santa's guidelines for each phase
- Age-specific language adaptations
- Greeting templates
- Quality metrics

**No code changes needed!** Just edit the YAML file.

## Deployment to Railway

### Prerequisites

1. **Get Tavus Credentials:**
   - Go to https://platform.tavus.io/
   - Profile → API Keys → Create new key
   - Go to Personas → Find Santa → Copy Persona ID

### Deploy Steps

1. **Initialize Railway project:**
   ```bash
   cd /home/alex31416/projects/aisanta/santa-api
   railway init
   ```

2. **Set environment variables:**
   ```bash
   railway variables set TAVUS_API_KEY=your_api_key_here
   railway variables set TAVUS_PERSONA_ID=your_persona_id_here
   ```

3. **Deploy:**
   ```bash
   railway up
   ```

4. **Get URL:**
   ```bash
   railway domain
   ```

5. **Test health endpoint:**
   ```bash
   curl https://your-service.up.railway.app/api/health
   ```

### Expected Health Response

```json
{
  "status": "healthy",
  "service": "santa-api",
  "version": "1.0.0",
  "configuration": {
    "tavus_api_key_set": true,
    "tavus_persona_id_set": true,
    "conversation_arcs_loaded": true,
    "arcs_available": ["5min", "10min"]
  },
  "tavus_api_reachable": true,
  "total_calls_tracked": 0
}
```

## Frontend Integration

### Example React Component

```jsx
import { useState } from 'react';

export default function SantaCall({ childName, childAge }) {
  const [callUrl, setCallUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [duration, setDuration] = useState('5min');

  const startCall = async () => {
    setLoading(true);

    try {
      const response = await fetch('https://santa-api.up.railway.app/api/santa/start-call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          child_name: childName,
          child_age: childAge,
          call_duration: duration,
          parent_email: 'parent@example.com'  // Optional
        })
      });

      const data = await response.json();
      setCallUrl(data.conversation_url);

      // Track when call ends
      setTimeout(() => {
        completeCall(data.conversation_id);
      }, duration === '5min' ? 300000 : 600000);

    } catch (error) {
      console.error('Error:', error);
      alert('Failed to start call');
    } finally {
      setLoading(false);
    }
  };

  const completeCall = async (conversationId) => {
    // Record completion for analytics
    await fetch('https://santa-api.up.railway.app/api/santa/complete-call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        actual_duration_seconds: 295,
        parent_rating: 5,
        child_enjoyed: true
      })
    });
  };

  return (
    <div>
      {!callUrl ? (
        <div>
          <h2>Call Santa!</h2>
          <select value={duration} onChange={(e) => setDuration(e.target.value)}>
            <option value="5min">5 Minute Call</option>
            <option value="10min">10 Minute Call</option>
          </select>
          <button onClick={startCall} disabled={loading}>
            {loading ? 'Connecting...' : 'Start Call'}
          </button>
        </div>
      ) : (
        <iframe
          src={callUrl}
          width="100%"
          height="600px"
          allow="camera; microphone"
        />
      )}
    </div>
  );
}
```

## Architecture

```
React Frontend
    ↓
    POST /api/santa/start-call
    {child_name, child_age, call_duration}
    ↓
Santa API (Railway)
    ├─ Load conversation arc (YAML)
    ├─ Generate greeting
    ├─ Create system prompt
    ├─ Call Tavus API
    └─ Track analytics
    ↓
Tavus API
    ├─ Create conversation
    ├─ Start video call
    └─ Return conversation_url
    ↓
Frontend displays video iframe
Child talks to Santa! 🎅
    ↓
Call ends
    ↓
POST /api/santa/complete-call
Analytics recorded ✅
```

## Customization

### Update Conversation Arcs

Edit `conversation-arcs.yaml`:

```yaml
arcs:
  5min:
    phases:
      - name: "greeting"
        duration_seconds: 30
        goals:
          - "Your custom goal here"
        santa_guidelines:
          - "Your custom guideline"
```

### Update Greeting Templates

Edit `conversation-arcs.yaml`:

```yaml
greeting_templates:
  ages_5_8:
    - "Ho ho ho! {child_name}! Custom greeting!"
```

### Add New Duration

Add to `conversation-arcs.yaml`:

```yaml
arcs:
  15min:
    name: "Extended Santa Experience"
    total_duration_seconds: 900
    phases:
      # Define phases...
```

Update validation in `main.py`:

```python
@validator('call_duration')
def validate_duration(cls, v):
    if v not in ['5min', '10min', '15min']:
        raise ValueError("Invalid duration")
    return v
```

## Monitoring

### View Analytics Dashboard

The main dashboard (https://dashboard-production-f03f.up.railway.app) can be extended to show Santa API analytics.

### Railway Logs

```bash
cd /home/alex31416/projects/aisanta/santa-api
railway logs
```

### Health Check

```bash
watch -n 5 curl -s https://santa-api.up.railway.app/api/health
```

## Troubleshooting

### "Tavus API credentials not configured"

Set environment variables:
```bash
railway variables set TAVUS_API_KEY=your_key
railway variables set TAVUS_PERSONA_ID=your_id
```

### "Arc not found"

Ensure `conversation-arcs.yaml` is included in deployment:
```bash
git add conversation-arcs.yaml
git commit -m "Add arcs"
railway up
```

### Tavus API errors

Check Tavus dashboard: https://platform.tavus.io/
- Verify API key is active
- Verify persona ID exists
- Check account limits/quotas

## Testing

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TAVUS_API_KEY=your_key
export TAVUS_PERSONA_ID=your_id

# Run server
uvicorn main:app --reload --port 8000

# Test endpoints
curl http://localhost:8000/api/health
```

### Test Start Call

```bash
curl -X POST http://localhost:8000/api/santa/start-call \
  -H "Content-Type: application/json" \
  -d '{
    "child_name": "Test Child",
    "child_age": 7,
    "call_duration": "5min"
  }'
```

## Production Checklist

- [ ] Deploy to Railway
- [ ] Set environment variables
- [ ] Test health endpoint
- [ ] Test start-call endpoint
- [ ] Update frontend with API URL
- [ ] Test end-to-end flow
- [ ] Monitor first 10 calls
- [ ] Set up error alerting
- [ ] Document API for team

## Support

- **Technical Spec:** `/home/alex31416/projects/aisanta/TAVUS-FRONTEND-INTEGRATION-SPEC.md`
- **Dashboard:** https://dashboard-production-f03f.up.railway.app
- **Railway Dashboard:** https://railway.app/dashboard
- **Tavus Dashboard:** https://platform.tavus.io/

---

**Status:** ✅ Ready for deployment
**Version:** 1.0.0
**Last Updated:** 2025-10-29
