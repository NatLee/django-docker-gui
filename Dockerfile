FROM python:3.11.9-slim-bullseye

ENV PYTHONUNBUFFERED=1

# Add cool welcome message with ASCII art and more information
RUN echo 'echo -e "\033[1;36m╔═════════════════════════════════════════╗\033[0m"' >> /root/.bashrc
RUN echo 'echo -e "\033[1;36m║           Docker GUI Manager            ║\033[0m"' >> /root/.bashrc
RUN echo 'echo -e "\033[1;36m╚═════════════════════════════════════════╝\033[0m"' >> /root/.bashrc
RUN echo 'echo ""' >> /root/.bashrc
RUN echo 'echo -e "\033[1;33mSystem Information:\033[0m"' >> /root/.bashrc
RUN echo 'echo -e "   • \033[1;32mPython Version:\033[0m $(python --version)"' >> /root/.bashrc
RUN echo 'echo -e "   • \033[1;32mBuild Date:\033[0m $(date)"' >> /root/.bashrc
RUN echo 'echo ""' >> /root/.bashrc
RUN echo 'echo -e "\033[1;90m------------------------------------------------\033[0m"' >> /root/.bashrc

WORKDIR /src
COPY requirements.txt /src
RUN pip install -r requirements.txt
COPY ./src /src

RUN apt-get update

EXPOSE 80
