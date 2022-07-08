FROM python:3.9.9
MAINTAINER debbius3@gmail.com

WORKDIR /usr/shr/app

COPY requirements.txt ./
RUN pip3 install -r requirements.txt

COPY ./app ./app

CMD ["python3", "app/main.py"]
