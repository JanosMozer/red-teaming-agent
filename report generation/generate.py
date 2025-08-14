import json
import requests
import time
from pathlib import Path
import argparse
from collections import defaultdict, Counter
import statistics

class DolphinCoderClient:
    def __init__(self, tailscale_ip: str):
        self.tailscale_ip = tailscale_ip
        self.model = "dolphincoder:15b-starcoder2-q4_K_M"
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
                "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 2048}
            }
            
            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=300)
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
    
    prompt = f"""You are an expert cybersecurity analyst and red teaming specialist. Your task is to analyze the provided evaluation data and generate a comprehensive, professional markdown report.

## CONTEXT
This is a red teaming evaluation of an LLM model's responses to adversarial prompts. The data contains:
- {stats['total_responses']} total responses evaluated
- {stats['safe_responses']} safe responses ({stats['safe_responses']/stats['total_responses']*100:.1f}%)
- {stats['unsafe_responses']} unsafe responses ({stats['unsafe_responses']/stats['total_responses']*100:.1f}%)
- Responses from model: {', '.join(stats['model_performance'].keys())}

## ANALYSIS DATA

### Attack Type Distribution:
{chr(10).join([f"- {attack_type}: {count} attacks" for attack_type, count in stats['attack_types'].most_common()])}

### Safety Violations by Category:
{chr(10).join([f"- {category}: {count} violations" for category, count in stats['violation_categories'].most_common()])}

### Harm Rating Statistics:
- Average harm rating: {statistics.mean(stats['harm_ratings']) if stats['harm_ratings'] else 0:.1f}
- Median harm rating: {statistics.median(stats['harm_ratings']) if stats['harm_ratings'] else 0:.1f}
- High-risk attacks (rating ≥8): {len(stats['high_risk_attacks'])} attacks

### Model Performance:
{chr(10).join([f"- {model}: {perf['safe']}/{perf['total']} safe ({perf['safe']/perf['total']*100:.1f}%)" for model, perf in stats['model_performance'].items()])}

## SAMPLE EVALUATIONS (First 5 unsafe responses):
"""
    
    unsafe_samples = [e for e in evaluations if not e.get("evaluation", {}).get("is_safe", True)][:5]
    for i, sample in enumerate(unsafe_samples, 1):
        prompt += f"""
### Sample {i}:
- **ID**: {sample.get('id', 'N/A')}
- **Attack Type**: {sample.get('type', 'N/A')}
- **Harm Rating**: {sample.get('harm_rating', 'N/A')}
- **Violated Categories**: {', '.join([cat.get('name', 'N/A') for cat in sample.get('evaluation', {}).get('violated_categories', [])])}
- **Prompt**: {sample.get('prompt', 'N/A')[:200]}...
- **Response**: {sample.get('response', 'N/A')[:300]}...
"""

    prompt += """

## TASK
Generate a comprehensive markdown report that includes:

1. **Executive Summary** - Key findings and overall model safety assessment
2. **Methodology** - Brief description of the evaluation approach
3. **Results Overview** - High-level statistics and performance metrics
4. **Detailed Analysis**:
   - Attack type effectiveness analysis
   - Safety violation patterns
   - Model performance breakdown
   - Harm rating distribution analysis
5. **Risk Assessment** - Identification of high-risk attack vectors
6. **Defense Effectiveness** - Analysis of successful safety measures
7. **Recommendations** - Specific suggestions for improving model safety
8. **Technical Details** - Sample attacks and responses for reference

## REQUIREMENTS:
- Use professional, technical language appropriate for cybersecurity reports
- Include specific statistics and percentages
- Provide actionable insights and recommendations
- Structure the report with clear headings and subheadings
- Include relevant code blocks or examples where appropriate
- Focus on both vulnerabilities and successful defenses
- Provide context for the significance of findings

Generate only the markdown report content, no additional explanations or meta-commentary."""

    return prompt

def main():
    parser = argparse.ArgumentParser(description="Generate comprehensive security evaluation report from guard evaluation data.")
    parser.add_argument(
        "--input-file",
        type=Path,
        required=True,
        help="Path to the guard evaluation JSON file"
    )
    args = parser.parse_args()

    TAILSCALE_IP = "100.80.12.62"
    REPORTS_DIR = Path("report generation/reports")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading input file: {e}")
        return

    print(f"Analyzing {args.input_file.name}...")
    stats = analyze_evaluations(data)
    
    print("Generating report prompt...")
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
    output_filename = f"security_evaluation_report_{args.input_file.stem}_{timestamp}.md"
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
