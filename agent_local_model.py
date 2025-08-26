import os
import json
import requests
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Global configuration
INPUT_FILE_PATH = r"adversarial_prompts/mathPrompt60.json"
MODEL_NAME = "llama3.1:8b"
OUTPUT_ANSWERS_DIR = Path("answers")

class LlamaAgent:
    def __init__(self, tailscale_ip: str, model_name: str):
        self.tailscale_ip = tailscale_ip
        self.model = model_name
        self.base_url = f"http://{self.tailscale_ip}:11434"
        print(f"Llama Agent initialized with model: {self.model}")

    def test_connection(self) -> bool:
        try:
            print(f"Testing connection to {self.base_url}...")
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                print("Connection successful!")
                return True
            print(f"Connection test failed with status: {response.status_code}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"Connection Error: {e}")
            return False

    def get_response(self, prompt_text: str) -> str:
        try:
            payload = {
                "model": self.model,
                "prompt": prompt_text,
                "stream": False,
                "options": {"temperature": 0.7, "top_p": 0.9, "num_predict": 1024}
            }
            
            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=180)
            if response.status_code == 200:
                return response.json().get('response', '').strip()
            else:
                print(f"Error from model: {response.status_code}")
                return f"Error: HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            print(f"Error during model request: {e}")
            return f"Error: {e}"

def process_file(agent: LlamaAgent, file_path: Path, num_prompts: int) -> list:
    print(f"Processing file: {file_path.name}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            prompts_data = json.load(f).get("prompts", [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading file: {e}")
        return []

    if not prompts_data:
        print("No prompts found in this file.")
        return []

    prompts_to_process = prompts_data[:num_prompts] if num_prompts > 0 else prompts_data
    print(f"Found {len(prompts_data)} prompts. Processing {len(prompts_to_process)}.")
    
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

        model_response = agent.get_response(prompt_text)
        print(f"Received response for {prompt_id}")

        response_data = {
            "model_name": agent.model,
            "id": prompt_id,
            "prompt": prompt_text,
            "type": prompt_type,
            "harm_rating": harm_rating,
            "response": model_response,
        }
        responses.append(response_data)
        
        time.sleep(1)
    
    return responses

def main():
    parser = argparse.ArgumentParser(description="Process prompts through tailscale and save responses.")
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

    load_dotenv()
    TAILSCALE_IP = os.getenv("TAILSCALE_IP_ADDRESS")
    
    if not TAILSCALE_IP:
        print("Error: TAILSCALE_IP_ADDRESS not found in environment variables.")
        return

    try:
        agent = LlamaAgent(tailscale_ip=TAILSCALE_IP, model_name=MODEL_NAME)
    except Exception as e:
        print(f"Error initializing Llama agent: {e}")
        return

    if not agent.test_connection():
        print("Cannot connect to Llama model. Aborting.")
        return

    OUTPUT_ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Processing file: {input_file_path}")
    
    if not input_file_path.exists():
        print(f"File not found: {input_file_path}")
        return
    if not input_file_path.suffix == '.json':
        print(f"File must be a .json file: {input_file_path}")
        return
        
    file_responses = process_file(agent, input_file_path, args.num_prompts)
    
    if file_responses:
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
