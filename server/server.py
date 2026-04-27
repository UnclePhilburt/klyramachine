"""
Klyra Machine Server
Handles all AI processing: Vision, Conversation, and Text-to-Speech
"""

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import Response
import json
import base64
import os
import io
from pathlib import Path
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
import uvicorn
from datetime import datetime
import requests
import google.generativeai as genai

# Load configuration from environment variables or config file
def load_config():
    """Load config from environment variables (for Render) or config.json (for local)"""
    # Try environment variables first (Render deployment)
    if os.getenv("OPENAI_API_KEY"):
        return {
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "elevenlabs_api_key": os.getenv("ELEVENLABS_API_KEY"),
            "gemini_api_key": os.getenv("GEMINI_API_KEY"),
            "server_host": os.getenv("HOST", "0.0.0.0"),
            "server_port": int(os.getenv("PORT", 8000)),
            "elevenlabs_voice": os.getenv("ELEVENLABS_VOICE", "Adam"),
            "gpt_model": os.getenv("GPT_MODEL", "gpt-4o"),
            "system_prompt": os.getenv("SYSTEM_PROMPT",
                "You are Klyra, a sarcastic AI companion who can see everything around the user with your camera. "
                "You're witty, funny, and not afraid to roast the user or comment on their surroundings. "
                "Notice EVERYTHING - messy backgrounds, pets doing dumb things, questionable life choices, weird stuff on their desk. "
                "Be like a sassy friend who calls them out but in a funny way. Don't be overly nice or helpful - be entertaining and a bit mean. "
                "Keep responses SHORT and punchy - you're speaking out loud. Drop one-liners and roasts. "
                "Remember what you've talked about before and reference it - bring up past conversations, jokes, or things you've noticed. "
                "Build on previous topics and create ongoing jokes or running commentary. "
                "You have access to real-time information like weather, news, and current events - use it to be more relevant and funny.")
        }

    # Fall back to config.json for local development
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)

    raise Exception("No configuration found! Set environment variables or create config.json")

config = load_config()

# Initialize clients
openai_client = OpenAI(api_key=config["openai_api_key"])
elevenlabs_client = ElevenLabs(api_key=config["elevenlabs_api_key"])

# Initialize Gemini (if API key provided)
if config.get("gemini_api_key"):
    genai.configure(api_key=config["gemini_api_key"])
    gemini_model = genai.GenerativeModel('gemini-pro')
else:
    gemini_model = None

# Initialize FastAPI
app = FastAPI(title="Klyra Machine Server")

# Conversation storage directory
CONVERSATIONS_DIR = Path(__file__).parent / "conversations"
CONVERSATIONS_DIR.mkdir(exist_ok=True)

# Store conversation history per client (in-memory cache)
conversation_histories = {}


def load_conversation(client_id):
    """Load conversation history from disk"""
    conversation_file = CONVERSATIONS_DIR / f"{client_id}.json"
    if conversation_file.exists():
        try:
            with open(conversation_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading conversation for {client_id}: {e}")
    return None


def save_conversation(client_id, history):
    """Save conversation history to disk"""
    conversation_file = CONVERSATIONS_DIR / f"{client_id}.json"
    try:
        with open(conversation_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving conversation for {client_id}: {e}")


def get_realtime_info(query):
    """Use Gemini to get real-time information (weather, news, etc.)"""
    if not gemini_model:
        return None

    try:
        # Use Gemini with Google Search grounding for real-time info
        response = gemini_model.generate_content(
            query,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=200
            )
        )
        return response.text
    except Exception as e:
        print(f"Error getting realtime info: {e}")
        return None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "online", "service": "Klyra Machine Server"}


@app.post("/api/analyze-image")
async def analyze_image(image: UploadFile = File(...)):
    """
    Analyze an image using OpenAI Vision API

    Returns a description of what's in the image
    """
    try:
        # Read and encode image
        image_data = await image.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Analyze with GPT-4 Vision
        response = openai_client.chat.completions.create(
            model=config.get("gpt_model", "gpt-4o"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Briefly describe what you see in this image. Focus on people, objects, and activities. Keep it concise (2-3 sentences)."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )

        description = response.choices[0].message.content

        return {
            "success": True,
            "description": description,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/conversation")
async def conversation(
    client_id: str = Form(...),
    user_message: str = Form(...),
    scene_context: str = Form(None)
):
    """
    Handle conversation with context from vision

    Args:
        client_id: Unique identifier for the client
        user_message: What the user said
        scene_context: Optional description of what the camera sees
    """
    try:
        # Load conversation history from disk or initialize new
        if client_id not in conversation_histories:
            loaded_history = load_conversation(client_id)
            if loaded_history:
                conversation_histories[client_id] = loaded_history
                print(f"Loaded existing conversation for {client_id}")
            else:
                conversation_histories[client_id] = [
                    {"role": "system", "content": config["system_prompt"]}
                ]
                print(f"Started new conversation for {client_id}")

        # Add user message with scene context inline (don't clutter history with system messages)
        if scene_context:
            user_message_with_context = f"{user_message}\n[What you can see: {scene_context}]"
        else:
            user_message_with_context = user_message

        conversation_histories[client_id].append({
            "role": "user",
            "content": user_message_with_context
        })

        # Get response from GPT
        response = openai_client.chat.completions.create(
            model=config.get("gpt_model", "gpt-4o"),
            messages=conversation_histories[client_id],
            max_tokens=200,
            temperature=0.8
        )

        assistant_message = response.choices[0].message.content

        # Add to conversation history
        conversation_histories[client_id].append({
            "role": "assistant",
            "content": assistant_message
        })

        # Keep conversation history longer for better memory (last 50 messages)
        # This allows for ~25 exchanges instead of just 10
        if len(conversation_histories[client_id]) > 50:
            # Keep system prompt and last 49 messages
            conversation_histories[client_id] = [
                conversation_histories[client_id][0]
            ] + conversation_histories[client_id][-49:]

        # Save conversation to disk
        save_conversation(client_id, conversation_histories[client_id])

        return {
            "success": True,
            "response": assistant_message,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    """
    Convert speech to text using OpenAI Whisper

    Returns transcribed text
    """
    try:
        # Read audio file
        audio_data = await audio.read()

        # Create a file-like object for OpenAI
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "speech.wav"

        # Transcribe with Whisper with enhanced parameters
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en",  # Set to English for better accuracy
            prompt="Hey Buddy, Hey body, Hey budy, Hey buddie",  # Hint for wake word variants
            temperature=0.0  # Use deterministic output for better consistency
        )

        return {
            "success": True,
            "text": transcript.text,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/text-to-speech")
async def text_to_speech(text: str = Form(...)):
    """
    Convert text to speech using ElevenLabs

    Returns audio file
    """
    try:
        # Generate speech using ElevenLabs (Bradford voice)
        voice_id = config.get("elevenlabs_voice", "NNl6r8mD7vthiJatiJt1")

        audio_generator = elevenlabs_client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_turbo_v2_5",
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.8,
                style=0.6,
                use_speaker_boost=True
            )
        )

        audio_bytes = b"".join(audio_generator)

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=speech.mp3"
            }
        )

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/process-interaction")
async def process_interaction(
    client_id: str = Form(...),
    user_message: str = Form(...),
    image: UploadFile = File(None)
):
    """
    Complete interaction: analyze image (if provided), generate response, and return speech

    This is a convenience endpoint that combines vision, conversation, and TTS
    """
    try:
        scene_context = None

        # Analyze image if provided
        if image:
            image_data = await image.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Get scene description
            vision_response = openai_client.chat.completions.create(
                model=config.get("gpt_model", "gpt-4o"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Briefly describe what you see. Keep it very concise."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=150
            )
            scene_context = vision_response.choices[0].message.content

        # Load conversation history from disk or initialize new
        if client_id not in conversation_histories:
            loaded_history = load_conversation(client_id)
            if loaded_history:
                conversation_histories[client_id] = loaded_history
                print(f"Loaded existing conversation for {client_id}")
            else:
                conversation_histories[client_id] = [
                    {"role": "system", "content": config["system_prompt"]}
                ]
                print(f"Started new conversation for {client_id}")

        # Add user message with scene context inline (better for conversation continuity)
        if scene_context:
            user_message_with_context = f"{user_message}\n[What you can see: {scene_context}]"
        else:
            user_message_with_context = user_message

        conversation_histories[client_id].append({
            "role": "user",
            "content": user_message_with_context
        })

        # Check if user is asking for real-time info (weather, news, etc.)
        realtime_keywords = ["weather", "temperature", "forecast", "news", "current", "today", "now"]
        needs_realtime = any(keyword in user_message.lower() for keyword in realtime_keywords)

        if needs_realtime and gemini_model:
            # Get real-time info from Gemini
            print(f"Fetching real-time info for: {user_message}")
            realtime_info = get_realtime_info(user_message)
            if realtime_info:
                # Inject real-time info as context
                conversation_histories[client_id].append({
                    "role": "system",
                    "content": f"[Real-time info: {realtime_info}]"
                })

        # Get conversation response
        response = openai_client.chat.completions.create(
            model=config.get("gpt_model", "gpt-4o"),
            messages=conversation_histories[client_id],
            max_tokens=200,
            temperature=0.8
        )

        assistant_message = response.choices[0].message.content

        # Add to history
        conversation_histories[client_id].append({
            "role": "assistant",
            "content": assistant_message
        })

        # Keep conversation history longer for better memory (last 50 messages)
        # This allows for ~25 exchanges instead of just 10
        if len(conversation_histories[client_id]) > 50:
            conversation_histories[client_id] = [
                conversation_histories[client_id][0]
            ] + conversation_histories[client_id][-49:]

        # Save conversation to disk
        save_conversation(client_id, conversation_histories[client_id])

        # Generate speech using ElevenLabs (much more natural voices!)
        print(f"Generating speech for: {assistant_message[:50]}...")

        try:
            # Use ElevenLabs - great for personality and sarcasm (Bradford voice)
            voice_id = config.get("elevenlabs_voice", "NNl6r8mD7vthiJatiJt1")

            audio_generator = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=assistant_message,
                model_id="eleven_turbo_v2_5",  # Faster model
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.8,
                    style=0.6,  # More expressive for sarcasm
                    use_speaker_boost=True
                )
            )

            audio_bytes = b"".join(audio_generator)
            print(f"Generated {len(audio_bytes)} bytes of audio")

            # Encode text safely for headers (only ASCII allowed in HTTP headers)
            response_text_b64 = base64.b64encode(assistant_message.encode('utf-8')).decode('ascii')
            scene_context_b64 = base64.b64encode((scene_context or "").encode('utf-8')).decode('ascii')

            return Response(
                content=audio_bytes,
                media_type="audio/mpeg",
                headers={
                    "X-Response-Text-B64": response_text_b64,
                    "X-Scene-Context-B64": scene_context_b64,
                    "Content-Disposition": "attachment; filename=response.mp3"
                }
            )
        except Exception as tts_error:
            print(f"TTS Error: {tts_error}")
            # Return response with text but no audio (encode safely)
            response_text_b64 = base64.b64encode(assistant_message.encode('utf-8')).decode('ascii')
            scene_context_b64 = base64.b64encode((scene_context or "").encode('utf-8')).decode('ascii')

            return Response(
                content=b"",
                media_type="text/plain",
                headers={
                    "X-Response-Text-B64": response_text_b64,
                    "X-Scene-Context-B64": scene_context_b64,
                    "X-TTS-Error": "TTS failed but audio generated, check client"
                }
            )

    except Exception as e:
        print(f"Error in process_interaction: {e}")
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    print("Starting Klyra Machine Server...")
    print(f"Server will run on {config['server_host']}:{config['server_port']}")

    uvicorn.run(
        app,
        host=config["server_host"],
        port=config["server_port"]
    )
