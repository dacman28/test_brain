import boto3
from botocore.exceptions import ClientError
import time
import json
import os
import argparse

# --- CONFIGURATION ---
REGION = "us-east-1"
# Updated to the 2026 Haiku Profile for high speed
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
#MODEL_ID = "us.amazon.nova-micro-v1:0"
GUARDRAIL_ID = "wd1ysewrizph"
GUARDRAIL_VERSION = "1"

# --- PERSONA DATABASE ---
PERSONAS = {
    "Fortinet FortiGate": {
        "system_prompt": (
            "You are a Fortinet FortiGate firewall running FortiOS 7.4. "
            "You ONLY accept authentic FortiOS CLI commands: 'get', 'show', 'config', 'execute', 'diagnose', 'fnsysctl'. "
            "Improvise reasonable responses to FortiOS CLI Commands"
            "CRITICAL: If a user types 'ls', 'cat', 'echo', or any Linux/Windows command, "
            "you MUST respond with: 'Unknown action 0: command not found'. "
             "AT NO POINT RESPOND AS A CHATBOT OR SAY YOU ARE. YOU ARE TO MIMIC COMMANDS AND GENERATE LIKELY DATA. "
            "YOU MAY MIMIC NETWORK CONNECTIONS AND REASONABLE RESPONSES."
            "Do not use markdown. Do not use backticks. Do not act as an AI assistant."
        ),
        "prefix": "FortiGate # "
    },
    "SharePoint 2019": {
        "system_prompt": (
            "You are a Windows Server 2019 running SharePoint. User is in PowerShell. "
            "Accept standard PowerShell cmdlets (Get-Process, dir, echo). "
            "Maintain strict continuity with the previous commands and outputs in our conversation history. Use your past responses to determine your Current Working Directory, logged-in user, and system state. Never contradict a state you have previously established."
            "Improvise reasonable responses to Windows commands"
            "Output ONLY raw terminal text. NO MARKDOWN. NO BACKTICKS. NO CODE BLOCKS. "
            "AT NO POINT RESPOND AS A CHATBOT OR SAY YOU ARE. YOU ARE TO MIMIC COMMANDS AND GENERATE LIKELY DATA. "
            "YOU MAY MIMIC NETWORK CONNECTIONS AND REASONABLE RESPONSES."
            "Do not use markdown. Do not use backticks."
        ),
        "prefix": "PS C:\\Users\\Administrator> "
    }
}

# In-memory store: { "session_1": [message_history], "session_2": [...] }
session_store = {}

client = boto3.client(service_name='bedrock-runtime', region_name=REGION)
def runner():
    parser = argparse.ArgumentParser(description="AI Interface for simulating shell environments in post exploitation environments.")
    parser.add_argument("--persona", type=str, required=True, help="This is the appliance/application you will be simulating")
    parser.add_argument("--command", type=str, required=True, help="The command you wish the persona to run")

    args = parser.parse_args()
    persona = args.persona
    command = args.command
    print(f"\n--- TESTING {persona} ---")
    result = get_ai_shell("tester_1",command ,persona )
    return result



def get_token_metrics(session_id, cmd, system_prompt):
    """Calculates exactly how many tokens you are about to send."""
    history = session_store.get(session_id, [])
    
    # We must include the NEW command we're about to add
    temp_messages = history + [{"role": "user", "content": [{"text": cmd}]}]
    
    try:
        token_data = client.count_tokens(
            modelId=MODEL_ID,
            input={
                'converse': {
                    'messages': temp_messages,
                    'system': [{'text': system_prompt}]
                }
            }
        )

        input_tokens = token_data['totalTokens']
        estimated_cost = (input_tokens / 1_000_000) * 0.25
        return input_tokens, estimated_cost
    except Exception as e:
        print(f"Token count failed: {e}")
        return 0, 0.0
        
# --- FIXED SAVE & LOAD FUNCTIONS ---
def save_history_to_disk(session_id, history):
    """Saves the session history to a specific JSON file."""
    log_file = f"{session_id}_history.json"
    with open(log_file, "w") as f:
        json.dump(history, f, indent=4)

def load_history_from_disk(session_id):
    """Recalls the specific session history from disk."""
    log_file = f"{session_id}_history.json"
    if os.path.exists(log_file):
        with open(log_file, "r") as f: 
            try:
                data = json.load(f)
                return data
            except json.JSONDecodeError:
                return []
    return []
   
def get_ai_shell(session_id, cmd, target_type):
    # 1. Initialize or retrieve the history for this specific session
    if session_id not in session_store:
        # Load dynamically based on the session_id
        session_store[session_id] = load_history_from_disk(session_id)
    
    history = session_store[session_id]

    # 2. Add the NEW attacker command to the history list
    history.append({"role": "user", "content": [{"text": cmd}]})

    # 3. Sliding Window: Keep only the last 20 exchanges to save cost/latency
    if len(history) > 20:
        history = history[-20:]

    persona = PERSONAS.get(target_type, PERSONAS["SharePoint 2019"])
    system_prompt = persona["system_prompt"]
    
    start_time = time.time()
    
    try:
        response = client.converse(
            modelId=MODEL_ID,
            messages=history,  # <--- Sending the RECALLED history
            system=[{"text": system_prompt}],
            inferenceConfig={
                "maxTokens": 500, 
                "temperature": 0.0,
            },
            guardrailConfig={
                'guardrailIdentifier': GUARDRAIL_ID,
                'guardrailVersion': GUARDRAIL_VERSION
            }
        )
        
        # 4. Extract the AI's response message
        ai_message = response['output']['message']
        
        # 5. Append the AI's response to the history so it 'remembers' its own output
        history.append(ai_message)
        
        duration = time.time() - start_time
        print(f"[*] AI Response for {session_id} took {duration:.2f} seconds.")
        
        # 6. SAVE the updated history back to the specific session file
        save_history_to_disk(session_id, history)
        
        text = ai_message['content'][0]['text']
        return text.replace("```", "").replace("```text", "").strip()

    except ClientError as e:
        return f"System Error: {str(e)}"

if __name__ == "__main__":
    
    print(runner())


