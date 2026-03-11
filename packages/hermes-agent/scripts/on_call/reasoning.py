import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODELS = ["Hermes-4-405B", "gpt-4o", "claude-3-5-sonnet"]

def get_model_opinion(model_name: str, context: str):
    client = OpenAI(
        base_url="https://inference-api.nousresearch.com/v1" if "Hermes" in model_name else None,
        api_key=os.getenv("NOUS_API_KEY") if "Hermes" in model_name else os.getenv("OPENAI_API_KEY")
    )
    
    prompt = f"System Incident Context: {context}\nAnalyze the root cause and suggest a fix."
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

def mixture_of_agents_debate(context: str):
    opinions = []
    print(f"Starting MoA debate with {len(MODELS)} agents...")
    for model in MODELS:
        try:
            opinion = get_model_opinion(model, context)
            opinions.append(f"Agent ({model}): {opinion}")
        except Exception as e:
            print(f"Failed to get opinion from {model}: {e}")

    # Final aggregator
    aggregator_client = OpenAI(
        base_url="https://inference-api.nousresearch.com/v1",
        api_key=os.getenv("NOUS_API_KEY")
    )
    
    discussion = "\n\n".join(opinions)
    aggregator_prompt = f"Following are opinions from different AI agents regarding a production incident:\n\n{discussion}\n\nBased on these, providing a final consensus root cause and optimized remediation plan."
    
    final_response = aggregator_client.chat.completions.create(
        model="Hermes-4-405B",
        messages=[{"role": "user", "content": aggregator_prompt}],
    )
    return final_response.choices[0].message.content

if __name__ == "__main__":
    ctx = "Error: Connection refused on port 8000. Memory usage is 95%. Last log: 'Out of Memory'."
    # print(mixture_of_agents_debate(ctx))
    print("MoA Reasoning Script loaded.")
