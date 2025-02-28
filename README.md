# Twilio Media Stream Server with OpenAI Integration

## Overview
Check frontend on: https://github.com/elderbug0/AI-customer-service_Frontend
This project is a FastAPI-based server that integrates Twilio Media Streams with OpenAI's Realtime API. The application enables:
- Managing and assigning Twilio phone numbers to users.
- Handling incoming calls via Twilio.
- Connecting Twilio's media streams to OpenAI's Realtime API for interactive voice and text processing.
- Dynamically setting business-specific instructions for voice interactions.

## Features

### 1. Twilio Integration
- **Incoming Call Handling**: When a call is received, it is connected to Twilio Media Stream.
- **Dynamic Twilio Number Assignment**: Assigns a unique Twilio number to each user dynamically.

### 2. OpenAI Realtime API Integration
- **Media Stream Processing**: Real-time processing of audio streams sent from Twilio.
- **Dynamic Instructions**: Reads instructions from a file to customize interactions.
- **Text and Audio Modality Support**: Supports both text and audio outputs from OpenAI.

### 3. FastAPI Backend
- **Endpoints**:
  - `/`: Health check endpoint.
  - `/set-instruction`: Allows dynamic setting of instructions for voice interactions.
  - `/assign-twilio-number`: Dynamically assigns Twilio phone numbers to users.
  - `/incoming-call`: Handles incoming Twilio calls and establishes a media stream connection.
  - `/media-stream`: WebSocket endpoint to process Twilio audio streams.
- **CORS Support**: Configured to allow all origins for easy testing and integration.

## Installation

### Prerequisites
- Python 3.9+
- Twilio account credentials (Account SID and Auth Token)
- OpenAI API key
- `.env` file with the following variables:
  ```plaintext
  OPENAI_API_KEY=<your_openai_api_key>
  TWILIO_ACCOUNT_SID=<your_twilio_account_sid>
  TWILIO_AUTH_TOKEN=<your_twilio_auth_token>
  TWILIO_WEBHOOK_URL=<your_twilio_webhook_url>
  PORT=5050
  ```

### Steps
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your credentials.
4. Start the server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 5050
   ```

## Usage

### Setting Business Instructions
Use the `/set-instruction` endpoint to configure custom instructions for voice interactions:
```bash
curl -X POST "http://localhost:5050/set-instruction" \
-H "Content-Type: application/json" \
-d '{
  "business_name": "My Business",
  "business_description": "Provides awesome services",
  "instruction": "Welcome to My Business! How can we assist you today?"
}'
```

### Assigning a Twilio Number
Assign a Twilio phone number to a user with the `/assign-twilio-number` endpoint:
```bash
curl -X POST "http://localhost:5050/assign-twilio-number" \
-H "Content-Type: application/json" \
-d '{
  "user_id": "user123"
}'
```

### Testing Incoming Calls
- Configure your Twilio number's webhook to point to `/incoming-call`.
- Make a call to your Twilio number and observe the media stream processing in action.

## WebSocket Media Stream
The `/media-stream` endpoint handles WebSocket connections between Twilio and OpenAI. It:
1. Receives audio from Twilio.
2. Sends the audio to OpenAI for processing.
3. Streams processed audio and text responses back to Twilio.

## File Structure
- `main.py`: The main application file.
- `instr.txt`: Stores dynamic instructions for voice interactions.
- `.env`: Environment variables for configuration.

## Dependencies
- **FastAPI**: For building the web server.
- **Twilio Python SDK**: For managing Twilio services.
- **Python-dotenv**: For environment variable management.
- **Uvicorn**: For running the FastAPI application.
- **Websockets**: For WebSocket communication with OpenAI.

## Error Handling
- Missing environment variables raise a `ValueError` at startup.
- Errors during endpoint execution return a JSON response with the error message.

## Future Enhancements
- Add authentication for endpoints.
- Support multiple languages for OpenAI interactions.
- Optimize audio processing latency.

## License
This project is open-source and available under the MIT License.

