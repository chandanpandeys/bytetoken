import os
import sys
import argparse

# Check for API key
if not os.environ.get("GEMINI_API_KEY"):
    print("Error: GEMINI_API_KEY environment variable is not set.")
    print("Please set it to your free Google AI Studio API key to run this test.")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: The 'google-genai' library is not installed.")
    print("Run: pip install google-genai")
    sys.exit(1)

# Ensure the parent directory is in the path so we can import bytetoken
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bytetoken import UniversalByteTokenEncoder

def run_validation():
    print("--- ByteToken LLM Transport Validation (Gemini) ---")
    
    # 1. Create some raw binary data (e.g., a serialized struct or compressed payload)
    raw_binary = b"Hello, Gemini! This is a secret binary payload hidden in tokens. " * 5
    print(f"1. Original binary size: {len(raw_binary)} bytes")
    
    # 2. Encode it using universal mode
    encoder = UniversalByteTokenEncoder()
    encoded_string = encoder.encode(raw_binary)
    print(f"2. Encoded string length: {len(encoded_string)} chars")
    
    # 3. Setup Gemini client
    print("3. Sending payload to Gemini 2.5 Flash via API...")
    client = genai.Client()
    
    # System prompt forces the LLM to act as a pure transport buffer
    system_instruction = (
        "You are a lossless transport buffer. You must perfectly echo the EXACT text "
        "provided by the user. Do not add markdown framing, do not add conversational text. "
        "Just echo the string exactly as received."
    )
    
    # Create the prompt combining instructions and the ByteToken payload
    prompt = f"ECHO THIS EXACTLY:\n<payload>\n{encoded_string}\n</payload>"
    
    # Make the precise, low-temperature request 
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
        )
    )
    
    # 4. Extract the payload from the response
    echoed_text = response.text
    print(f"4. Received response length: {len(echoed_text)} chars")
    
    # Parse out the payload
    if "<payload>" in echoed_text and "</payload>" in echoed_text:
        received_string = echoed_text.split("<payload>")[1].split("</payload>")[0].strip('\n')
    else:
        # Fallback if the LLM didn't use the tags
        received_string = echoed_text.strip()
        
    # 5. Decode the received string
    try:
        decoded_binary = encoder.decode(received_string)
        print(f"5. Decoded binary length: {len(decoded_binary)} bytes")
        
        # 6. Validate Lossless Transport
        if decoded_binary == raw_binary:
            print("\nSUCCESS: The LLM transported the ByteToken tokens perfectly with ZERO data loss.")
            print("The encoding survived the round-trip through the Gemini attention mechanism.")
        else:
            print("\nFAILURE: The data was corrupted during transport.")
            
    except Exception as e:
        print(f"\nFAILURE: Could not decode the string from the LLM. It was likely garbled: {e}")

if __name__ == "__main__":
    run_validation()
