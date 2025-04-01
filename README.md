# Autonomous Coding Workflow
## TLDR 🔴
```
git clone https://github.com/hem9984/Azlon-demo.git
cd Azlon-demo
```
```
echo "OPENAI_KEY=sk-..." > .env
```
```
docker compose up
```

* Frontend UI: http://localhost:8080/
* Restack UI: http://localhost:5233/runs

## All the codefiles for every run is saved in !!!
```Azlon-demo/llm-output``` 

### Usage in Frontend UI
1. Enter your user_prompt and test_conditions.
2. Click "Run Workflow".
3. Wait for your project code to complete!
* 🤖 It will recursively generate code, run the code, and fix the code if needed until it deems that your test case(s) are fulfilled.
-------------------------------------------------------------
## Overview
This project sets up an autonomous coding workflow using Restack, OpenAI’s GPT models, Docker-in-Docker for building and running Docker images, and a frontend React UI to interact with the system. Users can provide a user_prompt and test_conditions to generate code automatically, run it in a containerized environment, and validate the results. Users can also toggle an "advanced mode" to edit system prompts directly.

## Prerequisites
### Docker & Docker Compose:
* Ensure Docker (>= 20.10) and Docker Compose (>= 1.29) are installed.
* Install Docker | Install Docker Compose


# Usage
1. Open the frontend URL (http://localhost:8080/) in your browser.
   a. Also open http://localhost:5233/runs if you want to view the process in real-time!
2.  Enter your user_prompt and test_conditions.
   a. Toggle advanced mode if you want to modify the system prompts.
3. Click "Run Workflow".

#### The application will:
* Use your prompts to generate code and a Docker environment.
* Build and run the generated code in a container.
* Validate the output against test_conditions.
* Display the results in the frontend UI.
