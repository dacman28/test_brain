import boto3
from botocore.exceptions import ClientError
import time
import json
import os
import argparse
import uuid

# --- CONFIGURATION ---
REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
GUARDRAIL_ID = "wd1ysewrizph"
GUARDRAIL_VERSION = "1"

# --- SESSION MODE TOGGLE ---
SESSION_MODE = "amazon" 

# --- PERSONA DATABASE ---
PERSONAS = {
    "Fortinet FortiGate": {
        "system_prompt": "You are a Fortinet FortiGate firewall running FortiOS 7.4...",
        "prefix": "FortiGate # "
    },
    "sharepoint2019": {
        "system_prompt": "You are a Windows Server 2019 running SharePoint. User is in PowerShell...",
        "prefix": "PS C:\\Users\\Administrator> "
    }
}

# --- INITIALIZE DUAL CLIENTS ---
# Used for the Brain (Inference)
runtime_client = boto3.client(service_name='bedrock-runtime', region_name=REGION)
# Used for the Memory (Persistence)
agent_runtime_client = boto3.client(service_name='bedrock-agent-runtime', region_name=REGION)

# --- LOCAL JSON HISTORY LOGIC ---
def save_history_to_local(session_id, history):
    log_file = f"{session_id}_history.json"
    with open(log_file, "w") as f:
        json.dump(history, f, indent=4)

def load_history_from_local(session_id):
    log_file = f"{session_id}_history.json"
    if os.path.exists(log_file):
        with open(log_file, "r") as f: 
            try: return json.load(f)
            except json.JSONDecodeError: return []
    return []

# --- AMAZON CLOUD STORAGE LOGIC ---
def get_amazon_history(aws_uuid):
    """Fetches history list from the Bedrock Agent Runtime."""
    try:
        response = agent_runtime_client.get_session(sessionIdentifier=aws_uuid)
        # We store the JSON-stringified history in sessionMetadata
        metadata = response.get('sessionMetadata', {})
        history_str = metadata.get('chat_history', '[]')
        return json.loads(history_str)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            # Create session if it doesn't exist
            agent_runtime_client.create_session(sessionIdentifier=aws_uuid)
            return []
        raise e

def update_amazon_history(aws_uuid, history):
    """Saves history list to the Bedrock Agent Runtime."""
    try:
        # We store the history in sessionMetadata to bypass 'converse' parameter limits
        agent_runtime_client.update_session(
            sessionIdentifier=aws_uuid,
            sessionMetadata={
                'chat_history': json.dumps(history)
            }
        )
    except ClientError as e:
        print(f"AWS Session Update Failed: {e}")

# --- CORE LOGIC ---
def get_ai_shell(session_id, cmd, target_type):
    # Convert string to UUID for AWS
    aws_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, session_id))
    
    # 1. Load History
    if SESSION_MODE == "amazon":
        history = get_amazon_history(aws_uuid)
    else:
        history = load_history_from_local(session_id)

    # 2. Add User Command
    history.append({"role": "user", "content": [{"text": cmd}]})
    if len(history) > 20: history = history[-20:]

    persona = PERSONAS.get(target_type, PERSONAS["sharepoint2019"])
    system_prompt = persona["system_prompt"]
    start_time = time.time()

    try:
        # 3. Inference (Standard Converse call)
        response = runtime_client.converse(
            modelId=MODEL_ID,
            messages=history,
            system=[{"text": system_prompt}],
            inferenceConfig={"maxTokens": 500, "temperature": 0.0},
            guardrailConfig={
                'guardrailIdentifier': GUARDRAIL_ID,
                'guardrailVersion': GUARDRAIL_VERSION
            }
        )
        
        ai_message = response['output']['message']
        history.append(ai_message)

        # 4. Save History
        if SESSION_MODE == "amazon":
            update_amazon_history(aws_uuid, history)
        else:
            save_history_to_local(session_id, history)

        print(f"[*] AI Response ({SESSION_MODE} mode) took {time.time() - start_time:.2f}s")
        return ai_message['content'][0]['text'].strip()

    except ClientError as e:
        return f"System Error: {str(e)}"

def runner():
    parser = argparse.ArgumentParser(description="Deception AI Interface")
    parser.add_argument("--persona", type=str, required=True)
    parser.add_argument("--command", type=str, required=True)
    parser.add_argument("--session", type=str, default="attacker_01")
    
    args = parser.parse_args()
    return get_ai_shell(args.session, args.command, args.persona)

if __name__ == "__main__":
    print(runner())