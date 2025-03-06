# Autonomous Coding Workflow

# NEW WAY TO START SERVER
```bash
chmod +x start.sh
./start.sh
```
Uses Tailscale funnel instead of static ip addresses.
This way, any requests to https://muchnic.tail9dec88.ts.net/ go to your backend (port 8000).
Requests to https://muchnic.tail9dec88.ts.net:8443/ go to MinIO (port 9000).

## Backwards compatible way
Backwards compatible way: mkdir -p ./llm-output/input

docker compose up --build --remove-orphans


#### To exit
CTR + C then "docker compose down"



## Development Workflow
when server is up, can run:
```bash
cd backend
poetry run schedule
```
To run a simple example user input as if it was coming from the production frontend.

There is now a Makefile for running common commands. Run `make help` for a list of commands.

cleanup.sh just gets rid of unused imports.

There are also now extensive pytests

### Using the DevContainer (Recommended)

This project includes a DevContainer configuration that allows you to develop without needing to manually run docker-compose for each change. To use it:

1. Install the [Remote - Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension in VS Code
2. Open the project in VS Code
3. Click the green button in the bottom-left corner of VS Code
4. Select "Reopen in Container"

This will build and start the container defined in `docker-compose.yml` for you automatically and set up the development environment.

### Code Cleanup and Formatting

To maintain code quality, we've added several tools for code cleanup and formatting:

1. **Using the Makefile (in the container):**
   ```bash
   cd /app && make format
   ```

2. **Using the cleanup script (outside the container):**
   ```bash
   ./cleanup.sh
   ```

These commands will:
- Remove unused imports with `autoflake`
- Format code with `black`
- Sort imports with `isort`

### Running Tests

To run the test suite:

```bash
# Inside the container or with poetry installed locally
cd backend && make test
```


#### The application will:
* Use your prompts to generate code and a Docker environment.
* Build and run the generated code in a container.
* Validate the output against test_conditions.
* Display the results in the frontend UI and save the output files to Minio (S3 Bucket) and for backwords compatibility,on your local machine in ./llm-output.
