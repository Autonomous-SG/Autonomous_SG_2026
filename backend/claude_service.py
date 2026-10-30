import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"]
)

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")


def ask_claude(message: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system="You are a helpful AI assistant.",
        messages=[
            {
                "role": "user",
                "content": message
            }
        ]
    )

    return "".join(
        block.text
        for block in response.content
        if block.type == "text"
    )
