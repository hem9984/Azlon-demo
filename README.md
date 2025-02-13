# Autonomous Coding Workflow
## TLDR 🔴
```
git clone https://github.com/hem9984/Azlon-demo.git
cd Azlon-demo
mkdir -p ./llm-output/input
```
* PRO TIP: Bookmark llm-output and input directories in your file explorer for easy access
```
echo "OPENAI_API_KEY=sk-..." > .env
```
```
docker compose up --build --remove-orphans
```
* Frontend UI: http://localhost:8080/
* Restack UI: http://localhost:5233/
* Default output directory: ./Azlon-demo/llm-output

#### To exit
CTR + C then "docker compose down"

### Usage in Frontend UI
1. Enter your user_prompt and test_conditions. Optionally, add the files you wish it to start with in PATH_TO/llm-output/input
2. Click "Run Workflow".
3. Wait for your project code to complete! The final files will be saved to PATH_TO/llm-output/TIMESTAMP_OF_WORKFLOW on your local machine.
* 🤖 It will recursively generate code, run the code, and fix the code if needed until it deems that your test case(s) are fulfilled. 
-------------------------------------------------------------
## Overview
This project sets up an autonomous coding workflow using Restack, LLMs, Docker-in-Docker for building and running Docker images, and a frontend React UI to interact with the system. Users can provide a user_prompt and test_conditions to generate code automatically, run it in a containerized environment, and validate the results. Users can also toggle an "advanced mode" to edit system prompts directly.

## Prerequisites
### Docker & Docker Compose:
* Ensure Docker (>= 20.10) and Docker Compose (>= 1.29) are installed.
* Install Docker | Install Docker Compose


### The above commands will:

* Run Restack engine on http://localhost:5233 (and other ports as specified).
* Run the backend on http://localhost:8000
* Run the frontend on http://localhost:8080
* Check the docker-compose.yml and frontend/Dockerfile for the final frontend port and mode.

# SETUP DONE! YOU ARE READY TO USE 🎊

## Accessing the Application (open these two links in web browser windows):

#### Restack UI: http://localhost:5233/
The Restack UI will show you running workflows and other details.

#### Frontend UI: http://localhost:8080/
The React UI lets you enter your user_prompt and test_conditions. If you enable advanced mode in the GUI, you can edit system prompts as well.


#### The application will:
* Use your prompts to generate code and a Docker environment.
* Build and run the generated code in a container.
* Validate the output against test_conditions.
* Display the results in the frontend UI and save the output files on your local machine in ./llm-output.
