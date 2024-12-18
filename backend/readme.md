# To start restack engine
docker run -d --pull always --name restack -p 5233:5233 -p 6233:6233 -p 7233:7233 ghcr.io/restackio/restack:main

# to stop container
docker kill restack

# to remove stopped container
docker rm restack

# for reseting docker cache for development purposes
```
docker compose down -v
docker compose up --build
```
# TODO
friendly UI. add hardcode print statement at the bottom of the script everytime to enhance test case validation

----------------------------------------------


# restack instructions
* Set Poetry environment

poetry env use 3.12
* Open a shell to interact with the project:


poetry shell
​
* Install dependencies

poetry install
​
* Start your services that will execute the workflow in the background.


poetry run services
​
* Schedule the workflow in a separate shell
* In a separate terminal, schedule the workflow to start immediately.


poetry shell

poetry run schedule
​
Congratulations, you have run your first workflow
Visit the Developer UI to see your workflow already executed by the service: http://localhost:5233
(should allow user to edit the prompt and test cases and run within restack GUI)


​



# How to run summary:
* Change prompt and test cases in schedle_workflow.py to your project description
* Add pyproject.toml (and poetry.lock if you have one) in the project root.
* Set OPENAI_KEY as an environment variable.
