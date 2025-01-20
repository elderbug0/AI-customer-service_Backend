import os
import json
import base64
import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv
import websockets.client  
from fastapi.middleware.cors import CORSMiddleware
from twilio.rest import Client


load_dotenv()


SYSTEM_MESSAGE_FILE = "instr.txt"
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PORT = int(os.getenv('PORT', 5050))
VOICE = 'alloy'
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created'
]
SHOW_TIMING_MATH = False

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WEBHOOK_URL = os.getenv('TWILIO_WEBHOOK_URL')

if not all([OPENAI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WEBHOOK_URL]):
    raise ValueError("Missing necessary environment variables. Check your .env file.")


twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

user_twilio_numbers = {}  


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.post("/set-instruction")
async def set_instruction(request: Request):
    """Handle setting instructions and save them to the instr.txt file."""
    try:
        
        data = await request.json()
        business_name = data.get("business_name", "Unnamed Business")
        business_description = data.get("business_description", "No description provided.")
        instruction = data.get("instruction", "No instruction provided.")

        
        content = (
            f"Business Name: {business_name}\n"
            f"Business Description: {business_description}\n"
            f"Instruction: {instruction}\n"
        )

        
        with open(SYSTEM_MESSAGE_FILE, "w") as file:
            file.write(content)

        return JSONResponse({"message": "Instructions saved successfully."}, status_code=200)
    except Exception as e:
        return JSONResponse(
            {"detail": f"An error occurred while saving instructions: {e}"}, status_code=500
        )
@app.post("/assign-twilio-number")
async def assign_twilio_number(request: Request):
    """Assign a new Twilio phone number to the user."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        if not user_id:
            return JSONResponse({"error": "User ID is required"}, status_code=400)

        # Check if the user already has a Twilio number assigned
        if user_id in user_twilio_numbers:
            return JSONResponse(
                {
                    "message": "User already has a Twilio number assigned",
                    "twilio_number": user_twilio_numbers[user_id],
                },
                status_code=200,
            )

        available_numbers = twilio_client.available_phone_numbers("US").local.list(limit=1)
        if not available_numbers:
            return JSONResponse({"error": "No available Twilio numbers"}, status_code=500)

        
        twilio_number = available_numbers[0].phone_number
        purchased_number = twilio_client.incoming_phone_numbers.create(
            phone_number=twilio_number,
            voice_url=TWILIO_WEBHOOK_URL,  
        )

        
        user_twilio_numbers[user_id] = purchased_number.phone_number

        return JSONResponse(
            {
                "message": "Twilio number assigned successfully",
                "twilio_number": purchased_number.phone_number,
            },
            status_code=200,
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    response.say("Please wait while we connect your call")
    response.pause(length=1)
    response.say("OK you can start talking!")
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    print("Client connected")
    await websocket.accept()

    async with websockets.client.connect(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17',
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        await initialize_session(openai_ws)

        stream_sid = None
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []

        async def receive_from_twilio():
            """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
            nonlocal stream_sid, latest_media_timestamp
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data['event'] == 'media' and openai_ws.open:
                        latest_media_timestamp = int(data['media']['timestamp'])
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    elif data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        print(f"Incoming stream has started {stream_sid}")
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
            except WebSocketDisconnect:
                print("Client disconnected.")
                if openai_ws.open:
                    await openai_ws.close()

        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid, last_assistant_item
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    if response['type'] in LOG_EVENT_TYPES:
                        print(f"Received event: {response['type']}", response)

                    if response.get('type') == 'response.audio.delta' and 'delta' in response:
                        audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                        audio_delta = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": audio_payload
                            }
                        }
                        await websocket.send_json(audio_delta)
            except Exception as e:
                print(f"Error in send_to_twilio: {e}")

        await asyncio.gather(receive_from_twilio(), send_to_twilio())

async def initialize_session(openai_ws):
    """Control initial session with OpenAI."""
    try:
        with open(SYSTEM_MESSAGE_FILE, "r") as file:
            instructions = file.read().strip()
    except FileNotFoundError:
        instructions = "No instructions available."
    except Exception as e:
        instructions = f"Error reading instructions: {e}"

    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": instructions,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
        }
    }
    print('Sending session update:', json.dumps(session_update))
    await openai_ws.send(json.dumps(session_update))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
