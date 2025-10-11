FROM mcr.microsoft.com/vscode/devcontainers/base:ubuntu-24.04

RUN apt-get update && apt-get install -y curl git && apt-get clean

# Install Docker
RUN curl -fsSL https://get.docker.com | sh -

# Install Python 3.13
RUN apt-get update && apt-get -y install software-properties-common && apt-get clean
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get update && apt-get -y install python3-launchpadlib python3-pip && apt-get clean
RUN apt-get update && apt-get -y install python-is-python3 python3.13-full && apt-get clean

# Install Poetry
RUN apt-get update && apt-get install -y pipx && apt-get clean

USER vscode
RUN pipx install poetry
