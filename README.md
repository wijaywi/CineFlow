# 🎬 CineFlow AI: Autonomous Studio Pipeline

CineFlow AI is an enterprise-grade autonomous agent architecture that transforms rough scripts into release-ready video productions. Built on the **Google Cloud Agent Platform** and deeply integrated with **Grafana Cloud MCP**, CineFlow AI orchestrates adversarial agents (Director vs. Compliance) to ensure quality and safety standards are met before deterministic video rendering.

---

## ✨ Key Features

- **Grafana MCP Integration (Hackathon Requirement)**: Actively utilizes Grafana Cloud MCP at runtime to execute pre-flight incident checks and post-flight metrics queries, ensuring agents make decisions based on real-time Observability data.
- **Agent Governance & Zero-Trust Architecture**: Every action, API cost, and confidence score is strictly bound by an "Agent Constitution". The system automatically halts the project if budgets are exceeded or if an agent hallucinates.
- **Interactive Producer's Desk**: A visual, interactive Streamlit-based front-end to monitor the simulation and approve workflows.
- **Deterministic Rendering Pipeline**: Instead of relying on raw LLM APIs to blindly modify files, agents assemble a secure, verified *Timeline Manifest*, which is then strictly executed by an `ffmpeg` subprocess.

---

## 🛠️ Prerequisites

1. Python 3.9 or newer.
2. [FFmpeg](https://ffmpeg.org/download.html) installed and accessible from your system's `PATH` environment variable (required by `RenderAgent` and `QCAgent`).
3. Standard Python modules (runs locally).

---

## 🚀 Installation & Execution Guide

### 1. Install Dependencies
Open your Terminal or Command Prompt and navigate to the `src` directory:
```bash
cd "D:\src2\src"
```
Install the required library for the Web UI:
```bash
pip install streamlit
```

### 2. Run the Application (Producer's Desk UI)
Enter the following command to launch the interactive front-end:
```bash
python -m streamlit run app.py
```
*(Or `streamlit run app.py` if it's already in your PATH).*

Your browser will automatically open at `http://localhost:8501`.

### 3. How to Use the Application
1. **Configure Project**: On the left panel, leave the **Project ID** as default or enter a new one. Set your maximum **Budget**.
2. **Provide Direction**: In the **Semantic Script** text area, input your creative vision for the agents (e.g., `"Explain the new product and show traffic. Product Y is waterproof."`).
3. **Start Production**: Click the red **"Start Production"** button.
4. **Monitor Execution**: On the right panel, you can watch the logs in real-time (ranging from Grafana MCP Checks, FFprobe Ingestion, to the Director and Compliance Agent debate loops).
5. **Approval Gate**: Once the scenario's quality and safety (the Manifest) are approved by the Compliance agent, the process pauses. Click **"Approve and Render"** to authorize the system to export the final video.
6. **Completion**: If successfully validated and rendered, a video player will appear with a balloon animation 🎈. The final cost metrics will also be pulled directly from Grafana MCP.

*(Use the **"Reset Pipeline"** button on the left at any time if you want to start over with a different scenario).*

---

## 🏗️ Core Project Structure

- `app.py`: Main entry point for the Streamlit Web UI.
- `main.py`: Alternative entry point for Command Line (CLI) execution.
- `core/grafana_mcp.py`: Implementation of the Model Context Protocol (MCP) client to pull metrics and server health status from Grafana Cloud.
- `core/orchestrator.py`: The logic engine that controls agent iterations and budget constraints.
- `agents/`: Contains all modular agents (`director_agent`, `compliance_agent`, `render_agent`, `qc_agent`).
