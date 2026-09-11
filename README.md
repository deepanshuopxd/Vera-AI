# 🪄 Magicpin AI Challenge — Vera Bot

An AI-powered WhatsApp chatbot designed to help merchants (restaurants, salons, gyms, dentists, pharmacies) grow their businesses through hyper-personalized engagement and Google Business Profile optimization.

Built for the **Magicpin AI Challenge**, this server connects directly to the challenge's Judge Harness, composing AI-generated messages dynamically based on merchant payloads and handling complex multi-turn conversations.

## 🚀 Features

- **Hyper-Personalized LLM Composition**: Uses OpenAI's `gpt-4o` to craft specific, context-aware messages that adapt to the merchant's category (e.g. clinical for dentists, warm for salons).
- **FastAPI Core**: A high-performance async HTTP server that handles memory states and endpoints precisely according to the spec (`/v1/healthz`, `/v1/metadata`, `/v1/context`, `/v1/tick`, `/v1/reply`).
- **Edge-Case Handlers**: 
  - **Auto-Reply Loop Prevention**: Detects when it is speaking to an auto-responder and cuts off the conversation to prevent spam loops.
  - **Hostility Detection**: Instantly detects opt-outs and hostile replies, executing a graceful `end` action.
  - **Commitment Triggers**: Recognizes merchant commitments and seamlessly transitions to `binary_confirm_cancel` CTAs.
- **In-Memory State**: Manages contexts and conversational turns entirely in-memory for lightning-fast latency.

## 📁 Architecture

The bot's logic is fully decoupled into 4 modular components:

1. **`bot.py`**: The FastAPI server. Handles routing, endpoint specifications, and state memory.
2. **`composer.py`**: The LLM engine. Crafts the 4-context prompt (category, merchant, trigger, customer) and returns the JSON action payload.
3. **`reply_handler.py`**: The multi-turn engine. Uses regex rules for fast-path routing (hostile/auto-replies) and falls back to the LLM for complex, conversational replies.
4. **`config.py`**: Centralized configuration for LLM models, parameters, and application limits.

## 🛠️ Setup & Installation

**1. Create a Virtual Environment**
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

**2. Install Dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure your API Key**
Create a `.env` file in the root directory and add your OpenAI API key:
```env
OPENAI_API_KEY="sk-proj-your-api-key-here"
```

## 🏃 Running the Bot

Start the FastAPI server via Uvicorn:

```bash
uvicorn bot:app --host 0.0.0.0 --port 8080
```
The bot will spin up on `http://localhost:8080` and be ready to receive data from the judge simulator.

## 🧪 Testing with the Judge Simulator

While the `uvicorn` server is running in one terminal, open a new terminal, activate your virtual environment, and run the magicpin testing harness:

```bash
python judge_simulator.py
```

The judge will connect to your bot, simulate payloads, test the conversational edge-cases, and score the LLM's output.
