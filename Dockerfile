FROM python:latest
WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir -Ur requirements.txt

COPY . .