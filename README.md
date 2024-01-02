# Django Docker GUI

![demo](./doc/operation.gif)

A simple web UI for managing docker containers & images and interacting with using a fully functional terminal.

## Contains

- Django Web UI & xterm web terminal
- Split frontend & backend
- Django Channel with websocket for terminal & docker events
- Django-rq for docker async tasks

## Usage

> Docker daemon must be running.

1. Run the following command to get the image build and run.

```
docker-compose up
```

2. Create a superuser for Django admin.

> Check the script `./dev-create-superuser.sh` and change the username and password if you want.

```
bash dev-create-superuser.sh
```

3. Go to http://localhost:8000, it will show the login page.

## Reference

This repo was refactored from [MahmoudAlyy/docker-django-ui](https://github.com/MahmoudAlyy/docker-django-ui).

## License

[MIT](./LICENSE)

