FROM python:3.11.9-slim-bullseye

ENV PYTHONUNBUFFERED=1

WORKDIR /src
COPY requirements.txt /src
RUN pip install -r requirements.txt
COPY ./src /src

RUN apt-get update

EXPOSE 80

