# Auto Mode Autonomous Smart Contract Creation Coding Workflow
# LINUX ONLY INSTRUCTIONS, WILL NOT WORK ON MAC OR WINDOWS
```
git clone https://github.com/Pomu-io/Auto-Mode.git
cd Auto-Mode
```
```
echo "OPENAI_KEY=sk-...
WALLET_PRIVATE_KEY=0x1234...
WALLET_ADDRESS=0xABCD...
MODE_NETWORK=modeTestnet
CROSSMINT_API_KEY=aCrossmintKey
" > .env
```
```
docker compose up
```
* Frontend UI: http://localhost:8080/
* Restack UI: http://localhost:5233/

### Usage in Frontend UI
1. Enter your user_prompt and test_conditions.
2. Click "Run Workflow".
3. Wait for your project code to complete!
* 🤖 It will recursively generate code, run the code, and fix the code if needed until it deems that your test case(s) are fulfilled.

# About environment variables
* Passed from .env → Docker container → the Python backend
* Then exposed to the LLM in the prompt (i.e., the LLM knows it can use them)
* The LLM-generated Dockerfile / Node scripts will read them via process.env.WALLET_PRIVATE_KEY, process.env.CROSSMINT_API_KEY, etc.
