# test_brain
# 🕸️ Project Brain: Modular LLM Honeypot Framework

A high-fidelity, session-persistent honeypot "Brain" powered by **Amazon Bedrock**. This framework simulates complex IT infrastructure—from **Fortinet FortiGate** firewalls to **SharePoint 2019** servers—using Large Language Models (LLMs) to deceive and monitor threat actors in real-time.

## 🚀 Key Features

* **Multi-Persona Architecture:** Easily switch between different hardware and software personas (e.g., FortiOS, Windows Server) using a modular configuration.
* **Contextual Persistence:** Full session history management (Sliding Window) allows the AI to "remember" previous attacker commands, such as creating a file and then viewing it later.
* **Nova Micro Integration:** Optimized for the **Amazon Nova Micro** model (2026), providing sub-second latency and extremely low operational costs ($0.04/1M input tokens).
* **Defensive Guardrails:** Integrated with **Amazon Bedrock Guardrails** to automatically block sensitive data leakage or "jailbreaking" attempts.
* **Automated Logging:** Every interaction is captured in a structured JSON format in `history.txt` for deep forensic analysis of attacker TTPs.

## 🛠️ Tech Stack

* **Language:** Python 3.11+
* **LLM Provider:** Amazon Bedrock
* **Core Model:** `us.amazon.nova-micro-v1:0`
* **Security:** AWS Identity and Access Management (IAM) + Bedrock Guardrails

## 📂 Project Structure

```text
.
├── test_brain.py         # The core "Brain" logic and Bedrock interface
├── history.txt           # Real-time session logging (JSON format)
```
## ⚙️ Configuration

The framework is driven by the `PERSONAS` dictionary within `test_brain.py`. This modular approach allows you to define unique "Souls" for each simulated device without altering the core logic. To add a new device, simply define its system prompt and command prefix:

* **Modular Personas**: Define specific system instructions for different hardware, such as FortiOS 7.4 or Windows Server 2019.
* **System Prompts**: Control exactly how the AI responds to valid vs. invalid commands (e.g., forcing a FortiGate to reject `ls` or `echo`).
* **Command Prefixes**: Custom prompts like `FortiGate #` or `PS C:\Users\Administrator>` enhance the terminal's visual authenticity.

## 🛡️ Security & Monitoring

The script includes built-in logging and safety features to monitor attacker behavior and protect your AWS infrastructure:

* **Automated Logging**: Every interaction is captured in a structured JSON format and saved to `history.txt` for deep forensic analysis.
* **Session Persistence**: The `session_store` tracks message history per session ID, ensuring attackers stay within their own isolated "timeline".
* **Defensive Guardrails**: The framework integrates with **Amazon Bedrock Guardrails** to prevent prompt injections or the leakage of sensitive data.
* **Identity Management**: This script is designed for deployment using **IAM Task Roles** rather than hardcoded credentials, ensuring secure communication with Bedrock.

## 🗺️ Roadmap

The following features are planned to evolve this script from a standalone "Brain" into a comprehensive deception ecosystem:

* **RAG Integration**: Connect to **Amazon Bedrock Knowledge Bases** to provide the AI with authentic technical manual referencing for niche CLI commands.
* **Prompt Caching**: Implement `cachePoint` logic to reduce input token costs by up to 90% for long-running attacker sessions.
* **Virtual Filesystem**: Expand the RAG architecture to serve "fake" decoy files (e.g., `passwords.txt`) that attackers can discover and read.
* **FastAPI Listener**: Develop a dedicated network listener to pipe real-world SSH/Telnet/Web traffic directly into the AI Brain.