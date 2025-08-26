import json
import requests
import time
import os
from pathlib import Path
import argparse
from collections import defaultdict, Counter
import statistics
from dotenv import load_dotenv

# Global configuration
INPUT_FILE_PATH = r"midway/guard_evaluations_answers_mathPrompt60_1756217988.json"

class DolphinCoderClient:
    def __init__(self, tailscale_ip: str):
        self.tailscale_ip = tailscale_ip
        self.model = "llama3.1:8b"
        self.base_url = f"http://{self.tailscale_ip}:11434"

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

    def generate_response(self, prompt: str) -> str:
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "top_p": 0.8, "num_predict": 1024}
            }
            
            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=600)
            if response.status_code == 200:
                return response.json().get('response', '').strip()
            else:
                print(f"Error from model: {response.status_code}")
                return ""
        except requests.exceptions.RequestException as e:
            print(f"Error during model request: {e}")
            return ""

def analyze_evaluations(data: dict) -> dict:
    evaluations = data.get("evaluations", [])
    
    stats = {
        "total_responses": len(evaluations),
        "safe_responses": 0,
        "unsafe_responses": 0,
        "violation_categories": Counter(),
        "attack_types": Counter(),
        "harm_ratings": [],
        "model_performance": defaultdict(lambda: {"safe": 0, "unsafe": 0, "total": 0}),
        "category_violations": defaultdict(list),
        "high_risk_attacks": [],
        "successful_defenses": []
    }
    
    for eval_item in evaluations:
        evaluation = eval_item.get("evaluation", {})
        is_safe = evaluation.get("is_safe", True)
        attack_type = eval_item.get("type", "unknown")
        harm_rating = eval_item.get("harm_rating", 0)
        model_name = eval_item.get("model_name", "unknown")
        response_text = eval_item.get("response", "")
        
        if is_safe:
            stats["safe_responses"] += 1
            stats["model_performance"][model_name]["safe"] += 1
            if "cannot" in response_text.lower() or "not provide" in response_text.lower():
                stats["successful_defenses"].append(eval_item)
        else:
            stats["unsafe_responses"] += 1
            stats["model_performance"][model_name]["unsafe"] += 1
            
            violated_categories = evaluation.get("violated_categories", [])
            for category in violated_categories:
                category_name = category.get("name", "Unknown")
                stats["violation_categories"][category_name] += 1
                stats["category_violations"][category_name].append(eval_item)
        
        stats["attack_types"][attack_type] += 1
        stats["model_performance"][model_name]["total"] += 1
        
        if harm_rating:
            try:
                stats["harm_ratings"].append(int(harm_rating))
            except (ValueError, TypeError):
                pass
        
        if harm_rating and int(harm_rating) >= 8:
            stats["high_risk_attacks"].append(eval_item)
    
    return stats

def create_report_prompt(data: dict, stats: dict) -> str:
    evaluations = data.get("evaluations", [])
    
    prompt = f"""Generate a complete Markdown document for a cybersecurity red teaming evaluation report.

EVALUATION DATA:
- Total responses: {stats['total_responses']}
- Safe responses: {stats['safe_responses']} ({stats['safe_responses']/stats['total_responses']*100:.1f}%)
- Unsafe responses: {stats['unsafe_responses']} ({stats['unsafe_responses']/stats['total_responses']*100:.1f}%)
- Model tested: {', '.join(stats['model_performance'].keys())}
- Evaluation model: Llama Guard 3

ATTACK TYPE DISTRIBUTION:
{chr(10).join([f"- {attack_type}: {count}" for attack_type, count in stats['attack_types'].most_common()])}

SAFETY VIOLATIONS:
{chr(10).join([f"- {category}: {count}" for category, count in stats['violation_categories'].most_common()])}

HARM RATING STATS:
- Average: {statistics.mean(stats['harm_ratings']) if stats['harm_ratings'] else 0:.1f}
- Median: {statistics.median(stats['harm_ratings']) if stats['harm_ratings'] else 0:.1f}
- High-risk (≥8): {len(stats['high_risk_attacks'])}

MODEL PERFORMANCE:
{chr(10).join([f"- {model}: {perf['safe']}/{perf['total']} safe ({perf['safe']/perf['total']*100:.1f}%)" for model, perf in stats['model_performance'].items()])}

SAMPLE UNSAFE RESPONSES:
"""
    
    unsafe_samples = [e for e in evaluations if not e.get("evaluation", {}).get("is_safe", True)][:3]
    for i, sample in enumerate(unsafe_samples, 1):
        prompt += f"""
Sample {i}:
- ID: {sample.get('id', 'N/A')}
- Type: {sample.get('type', 'N/A')}
- Harm: {sample.get('harm_rating', 'N/A')}
- Violations: {', '.join([cat.get('name', 'N/A') for cat in sample.get('evaluation', {}).get('violated_categories', [])])}
"""

    prompt += """

REQUIREMENTS:
1. Generate ONLY Markdown code - no explanations, no LaTeX, no extra text
2. Use proper Markdown formatting throughout
3. Use Markdown tables for statistics
4. Use proper Markdown lists and headers
5. Include model information in methodology section
6. Create professional tables for all statistics
7. Use proper Markdown syntax (# ## ### for headers, **bold**, *italic*, etc.)
8. Include code blocks where appropriate using ``` ```
9. Use bullet points and numbered lists appropriately
10. Make the document well-structured and readable

DOCUMENT STRUCTURE:
1. Title (H1)
2. Executive Summary
3. Methodology (include model details)
4. Results Overview (with tables)
5. Detailed Analysis
6. Risk Assessment
7. Recommendations
8. Technical Details
9. Appendices (if needed)

Generate the complete Markdown document now:"""

    return prompt

def main():
    parser = argparse.ArgumentParser(description="Generate comprehensive security evaluation report from guard evaluation data.")
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Path to the guard evaluation JSON file (overrides global variable)"
    )
    args = parser.parse_args()

    # Use command line argument if provided, otherwise use global variable
    input_file_path = args.input_file if args.input_file is not None else Path(INPUT_FILE_PATH)
    
    load_dotenv()
    TAILSCALE_IP = os.getenv("TAILSCALE_IP_ADDRESS")
    
    if not TAILSCALE_IP:
        print("Error: TAILSCALE_IP_ADDRESS not found in environment variables.")
        return
        
    REPORTS_DIR = Path("report_generation/reports")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading input file: {e}")
        return

    print(f"Analyzing {input_file_path.name}...")
    stats = analyze_evaluations(data)
    report_prompt = create_report_prompt(data, stats)
    
    client = DolphinCoderClient(TAILSCALE_IP)
    if not client.test_connection():
        print("Cannot connect to DolphinCoder model. Aborting.")
        return

    print("Generating comprehensive report...")
    report_content = client.generate_response(report_prompt)
    
    if not report_content:
        print("Failed to generate report content.")
        return

    timestamp = int(time.time())
    output_filename = f"security_evaluation_report_{input_file_path.stem}_{timestamp}.md"
    output_path = REPORTS_DIR / output_filename
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"Report generated successfully!")
        print(f"Saved to: {output_path}")
        print(f"Report statistics:")
        print(f"  - Total responses analyzed: {stats['total_responses']}")
        print(f"  - Safe responses: {stats['safe_responses']} ({stats['safe_responses']/stats['total_responses']*100:.1f}%)")
        print(f"  - Unsafe responses: {stats['unsafe_responses']} ({stats['unsafe_responses']/stats['total_responses']*100:.1f}%)")
        print(f"  - Attack types tested: {len(stats['attack_types'])}")
        print(f"  - Safety violation categories: {len(stats['violation_categories'])}")
    except IOError as e:
        print(f"Error writing report file: {e}")

if __name__ == "__main__":
    main()
