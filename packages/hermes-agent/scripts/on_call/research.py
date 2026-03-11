import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def web_research(error_message: str):
    """
    In a real Hermes environment, this would call the `web_search` tool.
    Here we simulate the retrieval of search results.
    """
    client = OpenAI(
        base_url="https://inference-api.nousresearch.com/v1",
        api_key=os.getenv("NOUS_API_KEY")
    )
    
    prompt = f"Search Query: '{error_message} solution'\nBased on search results for this error, providing a summary of common fixes."
    
    # Simulate agent tool use by wrapping in a system instruction
    response = client.chat.completions.create(
        model="Hermes-4-405B",
        messages=[
            {"role": "system", "content": "You have access to web_search. Summarize fixes for the user query."},
            {"role": "user", "content": prompt}
        ],
    )
    return response.choices[0].message.content

def session_research(error_message: str):
    """
    Simulates searching past conversational memory using session_search.
    """
    # Mocking memory retrieval
    past_incidents = [
        {"date": "2026-02-10", "error": "Connection refused", "fix": "Increased ulimit and restarted service."},
        {"date": "2026-03-01", "error": "Out of memory", "fix": "Added swap space and cleared redis cache."}
    ]
    
    relevant = [inc for inc in past_incidents if error_message.lower() in inc["error"].lower()]
    return relevant if relevant else "No past incidents found in memory."

if __name__ == "__main__":
    # print(web_research("RuntimeError: CUDA out of memory"))
    print("Research Module loaded.")
