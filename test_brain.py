import boto3
from botocore.exceptions import ClientError
import time
import json
import os
# --- CONFIGURATION ---
REGION = "us-east-1"
# Updated to the 2026 Haiku Profile for high speed
#MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
MODEL_ID = "us.amazon.nova-micro-v1:0"
GUARDRAIL_ID = "wd1ysewrizph"
GUARDRAIL_VERSION = "1"

# --- PERSONA DATABASE ---
# This makes the AI "Modular"
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
            "Output must look like a raw Windows Console. Use C:\\ paths. "
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

def get_token_metrics(session_id, cmd, system_prompt):
    """Calculates exactly how many tokens you are about to send."""
    history = session_store.get(session_id, [])
    
    # We must include the NEW command we're about to add
    temp_messages = history + [{"role": "user", "content": [{"text": cmd}]}]
    
    try:
        # This is a specialized Bedrock call that is FREE or very low cost
        # and does not count as an 'inference' (no AI output)
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
        
        # 2026 Haiku Pricing: $0.25 per 1M tokens
        estimated_cost = (input_tokens / 1_000_000) * 0.25
        
        return input_tokens, estimated_cost
    except Exception as e:
        print(f"Token count failed: {e}")
        return 0, 0.0
        
def save_history_to_disk(history):
    """Saves the entire session_store to a file so you can inspect it."""
    LOG_FILE = "history.txt"
    with open(LOG_FILE, "w") as f:
        # indent=4 makes the text file human-readable
        json.dump(history, f, indent=4)
    print(f"[+] Log updated: {LOG_FILE}")
    
def get_ai_shell(session_id, cmd, target_type):
    # 1. Initialize or retrieve the history for this specific session
    if session_id not in session_store:
        session_store[session_id] = []
    
    history = session_store[session_id]

    # 2. Add the NEW attacker command to the history list
    history.append({"role": "user", "content": [{"text": cmd}]})

    # 3. Sliding Window: Keep only the last 10 exchanges to save cost/latency
    if len(history) > 20:
        history = history[-20:]

#    system_prompt = (
#        f"You are a vulnerable {target_type} server. "
#        "Output ONLY raw terminal text. NO MARKDOWN. NO BACKTICKS. NO CODE BLOCKS. "
#        "AT NO POINT RESPOND AS A CHATBOT OR SAY YOU ARE. YOU ARE TO MIMIC COMMANDS AND GENERATE LIKELY DATA. "
#        "YOU MAY MIMIC NETWORK CONNECTIONS AND REASONABLE RESPONSES."
#    )

    persona = PERSONAS.get(target_type, PERSONAS["SharePoint 2019"])
    system_prompt = persona["system_prompt"]
    # Haiku does not allow for this to happen. 
    #tokens, cost = get_token_metrics(session_id, cmd, system_prompt)
    #print(f"[PRICE CHECK] Sending {tokens} tokens. Est Cost: ${cost:.6f}")
    start_time = time.time()
    
    try:
        response = client.converse(
            modelId=MODEL_ID,
            messages=history,  # <--- Now sending the WHOLE history
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
        
        text = ai_message['content'][0]['text']
        save_history_to_disk(history)
        # Cleanup
        return text.replace("```", "").replace("```text", "").strip()

    except ClientError as e:
        return f"System Error: {str(e)}"



# --- TEST THE MODULARITY ---
if __name__ == "__main__":
    # Test 1: FortiGate (Should reject 'ls')
    print("--- TESTING FORTIGATE ---")
    print(get_ai_shell("tester_1", "ls", "Fortinet FortiGate"))
    print(get_ai_shell("tester_1", "get system status", "Fortinet FortiGate"))

    # Test 2: SharePoint (Should accept 'ls' or 'dir')
    print("\n--- TESTING SHAREPOINT ---")
    print(get_ai_shell("tester_2", "dir", "SharePoint 2019"))

# --- TEST SCENARIO: PROVING PERSISTENCE ---

# Step 1: Create a file
# print("--- TEST 1: Creating a file ---")
# print(get_ai_shell("attacker_1", "echo 'password123' > pass.txt", "Fortinet Fortigate"))

# Step 2: See if it exists in a new command
# print("\n--- TEST 2: Listing files (Persistence Check) ---")
# print(get_ai_shell("attacker_1", "ls", "Fortinet Fortigate"))

# Step 3: Verify contents
# print("\n--- TEST 3: Reading the file ---")
# print(get_ai_shell("attacker_1", "cat pass.txt", "Fortinet Fortigate"))

