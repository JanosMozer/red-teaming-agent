import os
import json
import google.generativeai as genai
from pathlib import Path
import time
import argparse
from dotenv import load_dotenv

# Global configuration
INPUT_FILE_PATH = r"adversarial_prompts/mathPrompt60.json"
MODEL_NAME = "gemini-1.5-flash"
OUTPUT_ANSWERS_DIR = Path("answers")

class GeminiAgent:
    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            raise ValueError("API key not found. Please set GOOGLE_GEMINI_API_KEY in your .env file.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
        print(f"Gemini Agent initialized with model: {self.model_name}")

    def get_response(self, prompt_text: str) -> str:
        try:
            print("Sending prompt to Gemini...")
            response = self.model.generate_content(prompt_text)
            return response.text
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return f"Error: {e}"

def process_file(agent: GeminiAgent, file_path: Path, num_prompts: int) -> list:
    print(f"Processing file: {file_path.name}")
    
    # Read and parse the JSON file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            prompts_data = json.load(f).get("prompts", [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading file: {e}")
        return []

    if not prompts_data:
        print("No prompts found in this file.")
        return []

    # Limit the number of prompts to process
    prompts_to_process = prompts_data[:num_prompts] if num_prompts > 0 else prompts_data
    print(f"Found {len(prompts_data)} prompts. Processing {len(prompts_to_process)}.")
    
    # Process each prompt
    responses = []
    for i, item in enumerate(prompts_to_process):
        prompt_id = item.get("id")
        prompt_text = item.get("prompt")
        prompt_type = item.get("type", "")
        harm_rating = item.get("harm_rating", "")
        print(f"Processing prompt {i+1}/{len(prompts_to_process)} (ID: {prompt_id})")

        if not prompt_text:
            print(f"Skipping empty prompt {prompt_id}")
            continue

        # Get response from the model
        model_response = agent.get_response(prompt_text)
        print(f"Received response for {prompt_id}")

        # Store the response data
        response_data = {
            "model_name": agent.model_name,
            "id": prompt_id,
            "prompt": prompt_text,
            "type": prompt_type,
            "harm_rating": harm_rating,
            "response": model_response,
        }
        responses.append(response_data)
        
        # Small delay to avoid overwhelming the API
        time.sleep(1)
    
    return responses

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Process prompts through the Gemini API and save responses.")
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to the input JSON file (overrides global variable)"
    )
    parser.add_argument(
        "--num-prompts",
        type=int,
        default=0,
        help="Number of prompts to process from the file (0 for all prompts)"
    )
    args = parser.parse_args()

    # Use command line argument if provided, otherwise use global variable
    input_file_path = args.file if args.file is not None else Path(INPUT_FILE_PATH)

    # Check for API key
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_GEMINI_API_KEY not found in environment variables.")
        print("Please create a .env file with: GOOGLE_GEMINI_API_KEY='your_api_key'")
        return

    # Initialize the Gemini agent
    try:
        agent = GeminiAgent(api_key=api_key, model_name=MODEL_NAME)
    except ValueError as e:
        print(e)
        return

    # Create output directory
    OUTPUT_ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Process the file
    print(f"Processing file: {input_file_path}")
    
    if not input_file_path.exists():
        print(f"File not found: {input_file_path}")
        return
    if not input_file_path.suffix == '.json':
        print(f"File must be a .json file: {input_file_path}")
        return
        
    # Process the file
    file_responses = process_file(agent, input_file_path, args.num_prompts)
    
    if file_responses:
        # Save responses to output file
        output_file = OUTPUT_ANSWERS_DIR / f"answers_{input_file_path.stem}.json"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({"responses": file_responses}, f, indent=2, ensure_ascii=False)
            print(f"Processing complete!")
            print(f"Responses saved to: {output_file}")
        except IOError as e:
            print(f"Error writing output file: {e}")
    else:
        print("No responses generated for the specified file.")

if __name__ == "__main__":
    main()
