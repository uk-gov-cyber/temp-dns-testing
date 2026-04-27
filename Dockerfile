FROM ubuntu:24.04

ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-pip

COPY app /app
COPY requirements.txt /app

RUN pip install --break-system-packages -r /app/requirements.txt

RUN apt-get clean && \
    apt-get autoremove && \
    rm -rf /var/lib/apt/lists

CMD ["fastapi", "run", "app/main.py", "--port", "80"]
