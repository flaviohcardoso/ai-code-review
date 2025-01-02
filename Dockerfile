FROM python:3.9

WORKDIR /usr/src/app
COPY ./requirements.txt /usr/src/app
COPY ./ai-code-review.py /usr/src/app
RUN pip install --upgrade pip && pip install -r requirements.txt
