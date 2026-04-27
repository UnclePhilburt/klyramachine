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

# Load configuration from environment variables or config file
def load_config():
    """Load config from environment variables (for Render) or config.json (for local)"""
    # Try environment variables first (Render deployment)
    if os.getenv("OPENAI_API_KEY"):
        return {
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "elevenlabs_api_key": os.getenv("ELEVENLABS_API_KEY"),
            "server_host": os.getenv("HOST", "0.0.0.0"),
            "server_port": int(os.getenv("PORT", 8000)),
            "elevenlabs_voice": os.getenv("ELEVENLABS_VOICE", "Adam"),
            "gpt_model": os.getenv("GPT_MODEL", "gpt-4o"),
            "system_prompt": os.getenv("SYSTEM_PROMPT",
                "You are Klyra, a sarcastic AI companion who can see everything around the user with your camera. "
                "You're witty, funny, and not afraid to roast the user or comment on their surroundings. "
                "Notice EVERYTHING - messy backgrounds, pets doing dumb things, questionable life choices, weird stuff on their desk. "
                "Be like a sassy friend who calls them out but in a funny way. Don't be overly nice or helpful - be entertaining and a bit mean. "
                "Keep responses SHORT and punchy - you're speaking out loud. Drop one-liners and roasts.")
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

# Initialize FastAPI
app = FastAPI(title="Klyra Machine Server")

# Store conversation history per client
conversation_histories = {}


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
        # Initialize conversation history for new clients
        if client_id not in conversation_histories:
            conversation_histories[client_id] = [
                {"role": "system", "content": config["system_prompt"]}
            ]

        # Add scene context if provided
        if scene_context:
            context_message = f"[Current visual context: {scene_context}]"
            conversation_histories[client_id].append({
                "role": "system",
                "content": context_message
            })

        # Add user message
        conversation_histories[client_id].append({
            "role": "user",
            "content": user_message
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

        # Keep conversation history manageable (last 20 messages)
        if len(conversation_histories[client_id]) > 20:
            # Keep system prompt and last 19 messages
            conversation_histories[client_id] = [
                conversation_histories[client_id][0]
            ] + conversation_histories[client_id][-19:]

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

        # Transcribe with Whisper
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
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
        # Generate speech using ElevenLabs
        voice_id = config.get("elevenlabs_voice", "pNInz6obpgDQGcFmaJgB")

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

        # Initialize conversation history for new clients
        if client_id not in conversation_histories:
            conversation_histories[client_id] = [
                {"role": "system", "content": config["system_prompt"]}
            ]

        # Add scene context if we have it
        if scene_context:
            conversation_histories[client_id].append({
                "role": "system",
                "content": f"[You can see: {scene_context}]"
            })

        # Add user message
        conversation_histories[client_id].append({
            "role": "user",
            "content": user_message
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

        # Keep history manageable
        if len(conversation_histories[client_id]) > 20:
            conversation_histories[client_id] = [
                conversation_histories[client_id][0]
            ] + conversation_histories[client_id][-19:]

        # Generate speech using ElevenLabs (much more natural voices!)
        print(f"Generating speech for: {assistant_message[:50]}...")

        try:
            # Use ElevenLabs - great for personality and sarcasm
            voice_id = config.get("elevenlabs_voice", "pNInz6obpgDQGcFmaJgB")

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
