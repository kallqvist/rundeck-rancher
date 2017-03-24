# Rundeck for Rancher

Dockerfile for Rundeck with custom python plugins for making Rundeck talk to the Rancher API.
Also installs Rundeck notification plugin for Slack.

### Forks
This repo is intended to be for building a self-contained docker image with both rundeck and this plugin installed in it.
My usecase for this is 100% based on docker together with rancher and that is what I want to streamline this repo for.

If you're looking to use this as an installable plugin directly in your already existing rundeck installation there is a fork that does just that and probably would be a much better starting point for you than what I have here.
Check it out!
https://github.com/ATIH/rundeck-rancher

I'll keep an eye on that plugin and if it seems to be progressing faster than the code here and also turns out to be flexible enough for me to be able to use for my pretty specific use-case I might rework this repo to simply be a Docker-file that installs their plugin instead.

#### EXPERIMENTAL
I run this in production myself for simple scheduling and backup jobs and it haven't failed me yet.
With that said; I use this at my own risk, you'll have to use it at your own!

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
