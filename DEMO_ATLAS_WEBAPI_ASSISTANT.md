
### Set up

Here are the steps needed to rerun the demonstration using Atlas Web API.

- Open-webui or an equivalent API has to running on port 3000

- Set these environment variables (or source .env if it is configures):
export OPENWEBUI_API_URL=http://localhost:3000/api/chat/completions  # might need to change this for llama.cpp-hosted models
export OPENWEBUI_API_KEY=
export OPENWEBUI_MODEL=
export FLASK_DEBUG=1


- SSH tunnel the port 5432 Postgres database on Triads-dl is tunneled to localhost 

- WebAPI has to be running. In order to do that you have to make sure that you set Java 8 as the environment. You have to run the maven command that does the spring boot. `mvn  spring-boot:run -Dmaven.test.skip=true -P webapi-postgresql -s WebAPIConfig/settings.xml -f pom.xml`

- run a Python HTTP server in the Atlas folder - Atlas is configured to talk to the Web API on my laptop when it's running on localhost

- the APC service has to be running and accessible (scripts/start_acp.sh). Now because I'm developing the ACP service in a containerized environment, you have to forward the port 7777 from the containerized environment onto the laptop local host.

### Demonstration:

- See [this video](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=70502f91-3594-4cb6-b776-b3bd012cf637)
