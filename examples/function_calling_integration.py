import os
import sys
import json

try:
    from openai import OpenAI
except ImportError:
    print("Error: The 'openai' library is not installed.")
    print("Run: pip install openai")
    sys.exit(1)

# Ensure the parent directory is in the path so we can import bytetoken
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bytetoken import UniversalByteTokenEncoder

def setup_mock_function(encoder):
    """
    This is the backend Python function that OpenAI will 'call'.
    It receives the ByteToken encoded string, decodes it back to raw bytes,
    and processes the data.
    """
    def process_image_data(encoded_image_bytes: str) -> str:
        try:
            # 1. Decode the received string back into raw bytes
            raw_bytes = encoder.decode(encoded_image_bytes)
            
            # (In a real app, you would process the raw_bytes image here)
            print(f"    [Backend Tool executing...] Successfully decoded {len(raw_bytes)} bytes of data!")
            
            # Simple validation for our example
            expected_prefix = b"\x89PNG\r\n\x1a\n"
            if raw_bytes.startswith(expected_prefix):
                return json.dumps({"status": "success", "message": "Valid PNG image received and processed."})
            else:
                 return json.dumps({"status": "error", "message": "Data does not look like a PNG."})
                 
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to decode: {e}"})
            
    return process_image_data

def run_function_calling_example():
    print("--- ByteToken OpenAI Tool Calling Example ---")
    
    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
         print("\nNote: GEMINI_API_KEY is not set. This example will run the local encoding steps")
         print("but will mock the actual API call to OpenAI.")
         client = None
    else:
         client = OpenAI()
    
    # 1. Setup encoder and our mock backend tool
    encoder = UniversalByteTokenEncoder()
    mock_backend_tool = setup_mock_function(encoder)
    
    # 2. Prepare the massive fake data payload
    # Let's say we have a 1MB PNG image we need the LLM to process via a tool
    fake_png_header = b"\x89PNG\r\n\x1a\n"
    fake_image_data = fake_png_header + (b"\x00\xFF" * 500_000) # ~1MB of binary zeroes and ones
    
    print(f"\n1. Original Binary Payload Size: {len(fake_image_data):,} bytes")
    
    # 3. Encode the data using ByteToken
    print("2. Encoding payload with ByteToken...")
    encoded_payload = encoder.encode(fake_image_data)
    ByteToken_tokens = int(len(fake_image_data) * 8 / 15) # Universal mode relies on space-prefixed atoms (~15 bits/token)
    print(f"3. Encoded Payload Token Length: ~{ByteToken_tokens:,} tokens")
    
    # Comparison: If we used Base64
    b64_tokens = int(len(fake_image_data) * 8 / 5.6) # Base64 yields ~5.6 bits per token on LLMs
    print(f"   (Compare to Base64: ~{b64_tokens:,} tokens. ByteToken saves you ~{b64_tokens - ByteToken_tokens:,} tokens!)")

    
    # 4. Define the tool schema for OpenAI
    tools = [
        {
            "type": "function",
            "function": {
                "name": "process_image_data",
                "description": "Process binary image data to detect objects.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "encoded_image_bytes": {
                            "type": "string",
                            "description": "The ByteToken-encoded binary bytes of the image.",
                        },
                    },
                    "required": ["encoded_image_bytes"],
                    "additionalProperties": False,
                },
                "strict": True
            }
        }
    ]
    
    print("\n4. Sending request to OpenAI API (with tool definition and encoded payload)...")
    
    if client:
        # Actually call OpenAI
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user", 
                    "content": f"Please process this image data and tell me what you see. Image data: {encoded_payload}"
                }
            ],
            tools=tools
        )
        
        message = response.choices[0].message
        
        if message.tool_calls:
            print(f"5. OpenAI successfully invoked the tool: {message.tool_calls[0].function.name}")
            print(f"   OpenAI packed the {len(message.tool_calls[0].function.arguments):,} chars of arguments.")
            
            # Execute the tool
            args = json.loads(message.tool_calls[0].function.arguments)
            tool_result = mock_backend_tool(args["encoded_image_bytes"])
            print(f"6. Backend python function result: {tool_result}")
    else:
        # Mock the API call response
        print("   [MOCK API] OpenAI received the prompt successfully.")
        print("   [MOCK API] OpenAI has decided to call the 'process_image_data' tool.")
        print("   [MOCK API] Handing tool arguments back to backend Python function...")
        
        # Execute the tool directly to simulate OpenAI returning the arguments
        tool_result = mock_backend_tool(encoded_payload)
        print(f"\n5. Backend python function result: {tool_result}")

if __name__ == "__main__":
    run_function_calling_example()
