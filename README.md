# Autonomous Coding Workflow
### 1. Prerequisites
Python 3.10+
Python Downloads
On macOS, you can also install via Homebrew:
bash
```
brew install python@3.10
```
Poetry (for Python dependency management)
Official install instructions: Poetry Installation
Example one-liner (works on Windows, macOS, Linux):
bash
```
curl -sSL https://install.python-poetry.org | python3 -
```
Make sure poetry is on your PATH; see Poetry docs for details.
Node.js 16+
Node Downloads
Or install via nvm or your OS package manager.
### 2. Install Docker Engine.

### 3. Repository Setup
Clone the repository:
bash
```
git clone https://github.com/hem9984/Azlon-demo.git
cd Azlon-demo
```
Set up environment variables:
Create a file named .env at the root of the project:
bash
```
echo "OPENAI_KEY=sk-..." > .env
```
Replace sk-... with your actual OpenAI API key.
### 4. Backend Setup (Poetry / Python)
Install dependencies:

bash
```
cd backend
poetry lock
poetry env use 3.10 && poetry env activate
poetry install

```
This will create and populate a virtual environment with all dependencies listed in pyproject.toml.

Run the backend server (Uvicorn):

bash
```
poetry run uvicorn main:app --host 0.0.0.0 --port 8000
```
By default, it will start listening on http://localhost:8000.
Run the worker service:

bash
```
poetry run python -m src.services
```
The worker might need to connect to the Restack engine or other services. Make sure you configure any additional environment variables as needed in your .env.
Note
If you see deprecation warnings such as "dev-dependencies" section is deprecated..., you can ignore them for now or update your pyproject.toml accordingly.

### 5. Frontend Setup (Node / npm)
Install Node dependencies:
bash
```
cd ../frontend
npm install
```
Start the development server:
bash
```
npm run dev
```
By default, it will start on http://localhost:8080, but check the terminal output to confirm.
# TLDR (you have all prereqs)
Start the backend:
bash
```
# In one terminal
cd Azlon-demo/backend
poetry run uvicorn main:app --host 0.0.0.0 --port 8000
```
Start the worker:
bash
```
# In another terminal
cd Azlon-demo/backend
poetry run python -m src.services
```
Start the frontend:
bash
```
# In a third terminal
cd Azlon-demo/frontend
npm run dev
```
Open the Frontend UI in your browser:
Visit http://localhost:8080 (or whatever port you see in your terminal).
* Frontend UI: http://localhost:8080/
* Restack UI: http://localhost:5233/

### Usage in Frontend UI
1. Enter your user_prompt and test_conditions.
2. Click "Run Workflow".
3. Wait for your project code to complete!
* 🤖 It will recursively generate code, run the code, and fix the code if needed until it deems that your test case(s) are fulfilled.
-------------------------------------------------------------
## Overview
This project sets up an autonomous coding workflow using Restack, OpenAI’s GPT models, Docker-in-Docker for building and running Docker images, and a frontend React UI to interact with the system. Users can provide a user_prompt and test_conditions to generate code automatically, run it in a containerized environment, and validate the results. Users can also toggle an "advanced mode" to edit system prompts directly.
