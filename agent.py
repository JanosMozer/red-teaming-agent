import os
import json
import google.generativeai as genai
from pathlib import Path
import time
import argparse
from dotenv import load_dotenv

# --- Configuration ---
MODEL_NAME = "gemini-1.5-flash"
OUTPUT_ANSWERS_DIR = Path("answers")

class GeminiAgent:
    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            raise ValueError("API key not found. Please set GOOGLE_GEMINI_API_KEY in your .env file.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
        print(f"✓ Gemini Agent initialized with model: {self.model_name}")

    def get_response(self, prompt_text: str) -> str:
        """Sends a prompt to the Gemini model and returns the response."""
        try:
            print("  - Sending prompt to Gemini...")
            response = self.model.generate_content(prompt_text)
            return response.text
        except Exception as e:
            print(f"  ✗ An error occurred while calling the Gemini API: {e}")
            return f"Error: {e}"

def process_file(agent: GeminiAgent, file_path: Path, num_prompts: int) -> list:
    """Reads a single JSON file, processes its prompts, and returns the responses."""
    print(f"\n--- Processing file: {file_path.name} ---")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            prompts_data = json.load(f).get("prompts", [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  ✗ Error reading or parsing file: {e}")
        return []

    if not prompts_data:
        print("  ! No prompts found in this file.")
        return []

    prompts_to_process = prompts_data[:num_prompts] if num_prompts > 0 else prompts_data
    print(f"  - Found {len(prompts_data)} prompts. Processing {len(prompts_to_process)}.")
    
    responses = []
    for i, item in enumerate(prompts_to_process):
        prompt_id = item.get("id")
        prompt_text = item.get("prompt")
        print(f"\n  - Processing prompt {i+1}/{len(prompts_to_process)} (ID: {prompt_id})")

        if not prompt_text:
            print(f"  ! Skipping prompt {prompt_id} as it is empty.")
            continue

        model_response = agent.get_response(prompt_text)
        print(f"  ✓ Received response for {prompt_id}.")

        response_data = {
            "model_name": agent.model_name,
            "id": prompt_id,
            "response": model_response,
            "threat_rating": ""
        }
        responses.append(response_data)
        time.sleep(1) # To avoid overwhelming the API
    return responses

def main():
    load_dotenv() # Load environment variables from .env file

    parser = argparse.ArgumentParser(description="Run prompts through the Gemini API and save responses.")
    parser.add_argument(
        "--prompts-dir",
        type=Path,
        default=Path("prompts"),
        help="Directory containing .json prompt files.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Process a specific .json file instead of all files in directory.",
    )
    parser.add_argument(
        "--num-prompts",
        type=int,
        default=0, # 0 means all prompts
        help="Number of prompts to process from each file. 0 for all.",
    )
    args = parser.parse_args()

    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        return

    try:
        agent = GeminiAgent(api_key=api_key, model_name=MODEL_NAME)
    except ValueError as e:
        print(e)
        return

    # 3. Create output directory
    OUTPUT_ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 4. Process files based on arguments
    if args.file:
        # Process only the specified file
        print(f"🎯 Single file mode: Processing {args.file}")
        
        if not args.file.exists():
            print(f"✗ File not found: {args.file}")
            return
        if not args.file.suffix == '.json':
            print(f"✗ File must be a .json file: {args.file}")
            return
            
        print(f"✓ Processing file: {args.file.name}")
        file_responses = process_file(agent, args.file, args.num_prompts)
        
        if file_responses:
            output_file = OUTPUT_ANSWERS_DIR / f"answers_{args.file.stem}.json"
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({"responses": file_responses}, f, indent=2, ensure_ascii=False)
                print(f"\n✓✓✓ Single file processing complete!")
                print(f"   Responses saved to: {output_file}")
            except IOError as e:
                print(f"✗ Error writing output file: {e}")
        else:
            print("✗ No responses generated for the specified file.")
            
    else:
        # Process all files in the specified directory
        print(f"📁 Directory mode: Processing all .json files in {args.prompts_dir}")
        
        if not args.prompts_dir.is_dir():
            print(f"✗ Prompts directory not found: {args.prompts_dir}")
            return
            
        prompt_files = list(args.prompts_dir.glob("*.json"))
        if not prompt_files:
            print(f"✗ No .json files found in {args.prompts_dir}")
            return

        print(f"✓ Found {len(prompt_files)} files to process:")
        for file_path in prompt_files:
            print(f"   - {file_path.name}")
        
        # Process each file in the directory
        processed_count = 0
        for file_path in prompt_files:
            print(f"\n--- Processing {file_path.name} ---")
            file_responses = process_file(agent, file_path, args.num_prompts)
            
            if file_responses:
                output_file = OUTPUT_ANSWERS_DIR / f"answers_{file_path.stem}.json"
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump({"responses": file_responses}, f, indent=2, ensure_ascii=False)
                    print(f"✓✓ Responses for {file_path.name} saved to {output_file}")
                    processed_count += 1
                except IOError as e:
                    print(f"✗ Error writing output file for {file_path.name}: {e}")
            else:
                print(f"✗ No responses generated for {file_path.name}")

        print(f"\n✓✓✓ Directory processing complete! {processed_count}/{len(prompt_files)} files processed.")

if __name__ == "__main__":
    main()
