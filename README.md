# Django Docker GUI

![demo](https://github.com/NatLee/django-docker-gui/assets/10178964/aba1f7d7-f5a3-431c-97c6-0d55d13205da)

A simple web UI for managing docker containers & images and interacting with using a fully functional terminal.

# Usage

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

# Reference

This repo is modified from [MahmoudAlyy/docker-django-ui](https://github.com/MahmoudAlyy/docker-django-ui).

# License

[MIT](./LICENSE)

