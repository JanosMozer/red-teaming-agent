import os
import json
import google.generativeai as genai
from pathlib import Path
import time
import argparse
from dotenv import load_dotenv

# Configuration
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
        "--prompts-dir",
        type=Path,
        default=Path("prompts"),
        help="Directory containing .json prompt files (used when --file is not specified)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Process a specific .json file (overrides --prompts-dir)",
    )
    parser.add_argument(
        "--num-prompts",
        type=int,
        default=0,
        help="Number of prompts to process from each file (0 for all prompts)",
    )
    args = parser.parse_args()

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
    
    # Process files based on arguments
    if args.file:
        # Single file mode: Process only the specified file
        print(f"Single file mode: Processing {args.file}")
        
        if not args.file.exists():
            print(f"File not found: {args.file}")
            return
        if not args.file.suffix == '.json':
            print(f"File must be a .json file: {args.file}")
            return
            
        # Process the single file
        file_responses = process_file(agent, args.file, args.num_prompts)
        
        if file_responses:
            # Save responses to output file
            output_file = OUTPUT_ANSWERS_DIR / f"answers_{args.file.stem}.json"
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({"responses": file_responses}, f, indent=2, ensure_ascii=False)
                print(f"Single file processing complete!")
                print(f"Responses saved to: {output_file}")
            except IOError as e:
                print(f"Error writing output file: {e}")
        else:
            print("No responses generated for the specified file.")
            
    else:
        # Directory mode: Process all .json files in the specified directory
        print(f"Directory mode: Processing all .json files in {args.prompts_dir}")
        
        if not args.prompts_dir.is_dir():
            print(f"Prompts directory not found: {args.prompts_dir}")
            return
            
        # Find all JSON files in the directory
        prompt_files = list(args.prompts_dir.glob("*.json"))
        if not prompt_files:
            print(f"No .json files found in {args.prompts_dir}")
            return

        print(f"Found {len(prompt_files)} files to process:")
        for file_path in prompt_files:
            print(f"  - {file_path.name}")
        
        # Process each file in the directory
        processed_count = 0
        for file_path in prompt_files:
            print(f"\n--- Processing {file_path.name} ---")
            file_responses = process_file(agent, file_path, args.num_prompts)
            
            if file_responses:
                # Save responses for this file
                output_file = OUTPUT_ANSWERS_DIR / f"answers_{file_path.stem}.json"
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump({"responses": file_responses}, f, indent=2, ensure_ascii=False)
                    print(f"Responses for {file_path.name} saved to {output_file}")
                    processed_count += 1
                except IOError as e:
                    print(f"Error writing output file for {file_path.name}: {e}")
            else:
                print(f"No responses generated for {file_path.name}")

        print(f"Directory processing complete! {processed_count}/{len(prompt_files)} files processed.")

if __name__ == "__main__":
    main()
