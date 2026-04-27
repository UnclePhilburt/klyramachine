"""
Vision module using OpenAI Vision API
Analyzes images and describes what it sees
"""

from openai import OpenAI


class VisionProcessor:
    """Handles vision processing with OpenAI Vision API"""

    def __init__(self, api_key):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=api_key)
        print("Vision processor initialized")

    def analyze_image(self, image_base64, prompt=None):
        """
        Analyze an image using GPT-4 Vision

        Args:
            image_base64: Base64 encoded image
            prompt: Optional custom prompt, otherwise uses default

        Returns:
            Description of what the AI sees
        """
        if prompt is None:
            prompt = (
                "Describe what you see in this image. "
                "Focus on people, objects, activities, and the overall scene. "
                "Be conversational and natural, as if you're talking to someone."
            )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # or gpt-4-turbo, gpt-4o-mini for lower cost
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
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
            return description

        except Exception as e:
            print(f"Error analyzing image: {e}")
            return None

    def get_scene_context(self, image_base64):
        """
        Get contextual information about the scene for conversation
        This helps the AI understand the environment for better responses
        """
        prompt = (
            "Briefly describe the setting, any people present, "
            "what they're doing, and any notable objects or activities. "
            "Keep it concise (2-3 sentences)."
        )
        return self.analyze_image(image_base64, prompt)


# Test the vision module
if __name__ == "__main__":
    import json

    print("Testing vision processor...")

    # Load config
    with open("config.json", 'r') as f:
        config = json.load(f)

    vision = VisionProcessor(config["openai_api_key"])

    # Test with a sample image (you'd need camera.py working first)
    print("Vision processor ready for testing with camera images")
