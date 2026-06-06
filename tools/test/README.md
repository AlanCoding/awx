### Integration Testing

This is a location intended to offer some community-directed integration testing.

It is very standard for projects to offer a docker image which allows testing
with the web service that the project provides.

You run these tests _outside_ of the container on your own machine.
You need to cd into the directory in order to pick up its unique pytest config.
These tests will pull images, run containers, and tear down the containers at the end.
These steps correspond to the `.github/workflows/ci_integration.yml` steps:

```
pip install -r tools/test/test_requirements.txt
cd tools/test/integration
py.test . -s
```

The `-s` will print stdout, which should include logs from the containers.

### Debugging Tips

If you insert a `pdb.set_trace()` into a test, you can catch it with the
severs running actively in the background.
The AWX server should be available at `http://localhost:8045/` (not https) with
a user/password combination of admin/password.

Static files (and many other things) are not expected to work.
