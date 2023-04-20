### Integration Testing

This is a location intended to offer some community-directed integration testing.

#### Minimal AWX

It is very standard for projects to offer a docker image which allows testing
with the web service that the project provides.
We have a set of tooling here which is intended to offer that for AWX itself.

The intended use case is to test an AWX container in conjunction with
another container from another integrated service.
A secondary goal is that someone might find this useful to co-develop their
own services, in their own repo, with AWX.

For a manual experience, you can try this:

```
docker run --interactive \
	--publish 8045:8045 \
	-u $(id -u) --privileged --rm \
	-v ./:/awx_devel \
	-v ./tools/test/minimal_settings.py:/etc/tower/conf.d/minimal_settings.py \
	-e AWX_LOGGING_MODE=stdout \
	-e DJANGO_SUPERUSER_PASSWORD=password \
	--name=hack_awx_1 \
	ghcr.io/ansible/awx_devel:devel /awx_devel/tools/test/test_server.sh awx-manage runserver 8045
```

This will give a server located at `http://localhost:8045/` (not https) with
a user/password combination of admin/password.

Getting static files working with this is still TBD (so no UI, only API).
Websockets are philosophically incompatible work with this approach.
This doesn't run a task system (you could attach your own at great effort),
and you can forget about receptor.
If you wanted any of these things, see the existing docker-compose stuff.

Running that `docker run` command will give an instance with a fresh database,
even skipping the normal course of running migrations.

### Automated Testing

This is still very raw, but it works in a sense.

```
pip install -r tools/test/test_requirements.txt
cd tools/test/integration
py.test . -s
```

That will run the AWX container.
