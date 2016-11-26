# Rundeck for Rancher

Dockerfile for Rundeck with custom python plugins for making Rundeck talk to the Rancher API.
Also installs Rundeck notification plugin for Slack.

### EXPERIMENTAL - Use at your own risk!

##### TTY must be disabled in Rancher for script execution or triggering of run-once service to function!
Plugins will raise exceptions otherwise but it might not be immediately obvious why it's doing that.

### Getting started
- For pre-built image head over to [DockerHub](https://hub.docker.com/r/kallqvist/rundeck-rancher/)
- Requires config and API keys specific to your Rancher installation.
- Check attached [docker-compose.yml](https://github.com/kallqvist/rundeck-rancher/blob/master/docker-compose.yml) for required config and how to run with persistant SQL backing store.
```
docker-compose up
# Direct your browser to http://127.0.0.1:4440
# Default username and password for Rundeck is admin / admin
```

## Rundeck plugins in this repo:
#### Rancher resource collector
- Using the Rancher API to fetch containers from a given Rancher environment ID and returning them as nodes to Rundeck.
- Can filter on Rancher stack name using a regex pattern.
- Can also filter containers to only return the first container from services in cases where service scale in Rancher is greater than one.

#### Rancher container script executor
- Using Rancher Rest-API and websockets to execute bash commands in already running containers (as returned by ResourceModelSource plugin).
- Will raise python Exception if any stderr output is found during websocket command execution to abort Rundeck job.

#### Rancher container file copier
- TBD, not yet functional!
- Seriously, don't use this yet!
- It will raise Exceptions...

#### Rancher trigger run-once container
- Using the Rancher Rest-API to trigger a run of a Rancher start-once service.
- Using Rancher event listener and logs websockets for parsing log output.
- Will raise python Exception if any stderr output is found in logs from start-once service run.


### Links:
- [Rundeck](http://rundeck.org/)
- [Rancher](http://rancher.com/rancher/)
- [Rundeck Slack plugin](https://github.com/higanworks/rundeck-slack-incoming-webhook-plugin)

### Merge requests
- Are very much welcome over at [GitHub](https://github.com/kallqvist/rundeck-rancher)!
