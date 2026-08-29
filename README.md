
# 🎬 CineFlow AI
<img width="800" height="800" alt="Cineflow_Logo" src="https://github.com/user-attachments/assets/ec007fdd-c52b-4cab-a25b-be097229c580" />
**Agentic Cinema Workflow Automation**

Welcome to **CineFlow AI**, an autonomous movie studio agent built for the **Agentic Cinema Hackathon**. CineFlow utilizes a multi-agent network to transform raw footage, A-Roll, and B-Roll into a seamless cinematic production.

## 🚀 Key Features & Hackathon Compliance

This project has been meticulously crafted to fulfill the core criteria of the Hackathon:

*   **Google Cloud ADK (Phase 1 & 4):** Powered natively by `google-cloud-aiplatform[agent_engines,adk]`. The `DirectorAgent` autonomously orchestrates tools and makes deterministic editing decisions.
*   **Grafana Labs MCP Integration (Phase 3):** Uses the official `mcp.client.sse` to connect to **Grafana Cloud**. The Director Agent performs *Forced Actions* to check for system incidents (`check_grafana_incidents`) and observability metrics before rendering the final manifest.
*   **Enterprise Guardrails & Truth Graph (Compliance):** Built-in legal and factual guardrails. The AI extracts claims from the Director's prompt and cross-references them with a corporate Knowledge Base (`truth_graph.py`). If a director requests a false claim (e.g., claiming a product is "waterproof" when it is only "water-resistant"), the agent halts the pipeline to prevent false advertising lawsuits.
*   **Gemini Multimodal Video Analysis (Phase 2):** Ingests raw video files to analyze scenes, flag dead-air, and extract metadata using Gemini 3.6 Flash.
*   **Audio & Speech Generation (Phase 2):** Automatically generates missing narrative voiceovers (`generate_voiceover` ADK Tool) and mixes them dynamically using FFmpeg.
*   **Safety Guardrails (Phase 5):** Hardcoded Gemini `SafetySettings` to block hate speech, harassment, and dangerous content.

## 🛠️ Technology Stack
*   **Core:** Python 3.9, Streamlit
*   **Agent Framework:** Google Cloud Agent Development Kit (ADK)
*   **Models:** Gemini 1.5 Pro (Reasoning), Gemini 3.6 Flash (Multimodal)
*   **Observability:** Grafana Cloud (via Model Context Protocol)
*   **Media Processing:** FFmpeg

## 📦 Local Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/wijaywi/CineFlow.git
    cd CineFlow
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set Environment Variables:**
    To use the full capabilities, ensure you have the following secrets configured:
    ```bash
    export GEMINI_API_KEY="your_api_key_here"
    export GRAFANA_MCP_ENDPOINT="your_grafana_mcp_url_here"
    export GRAFANA_API_KEY="your_grafana_token_here"
    ```

4.  **Run the Application:**
    ```bash
    streamlit run src/app.py
    ```

## 🌐 Deployment (Streamlit Community Cloud / Google Cloud Run)

This repository includes a `Dockerfile` for easy deployment to **Google Cloud Run**:
```bash
gcloud run deploy cineflow-ai --source . --region us-central1 --allow-unauthenticated
```
Alternatively, it can be deployed directly via **Streamlit Community Cloud** by linking this GitHub repository.

---
