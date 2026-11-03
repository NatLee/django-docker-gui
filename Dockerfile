FROM python:3.12-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Welcome message for the shells opened from the Terminal page
RUN printf '%s\n' \
    'echo -e "\033[1;36m╔═════════════════════════════════════════╗\033[0m"' \
    'echo -e "\033[1;36m║           Docker GUI Manager            ║\033[0m"' \
    'echo -e "\033[1;36m╚═════════════════════════════════════════╝\033[0m"' \
    'echo ""' \
    'echo -e "\033[1;33mSystem Information:\033[0m"' \
    'echo -e "   • \033[1;32mPython Version:\033[0m $(python --version)"' \
    "echo -e \"   • \033[1;32mBuild Date:\033[0m $(date -u '+%Y-%m-%d %H:%M UTC')\"" \
    'echo ""' \
    'echo -e "\033[1;90m------------------------------------------------\033[0m"' \
    >> /root/.bashrc

WORKDIR /src
COPY requirements.txt /src
RUN pip install -r requirements.txt
COPY ./src /src

EXPOSE 8000
