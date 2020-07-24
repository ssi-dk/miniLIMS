FROM amancevice/pandas:0.25.2-alpine
#FROM python:3.6.8-alpine3.9

LABEL MAINTAINER="Martin Basterrechea <mbas@ssi.dk>"

ENV GROUP_ID=1000 \
    USER_ID=1000

WORKDIR /var/www/

RUN apk add --no-cache --update python3-dev  gcc build-base

ADD . /var/www/
# ADD ./requirements.dev.txt /var/www/requirements.dev.txt


RUN pip3 install -r requirements.dev.txt
# ADD ./minilims /var/www/minilims
# ADD ./wsgi.py /var/www/

RUN pip3 install gunicorn
RUN addgroup -g $GROUP_ID www
RUN adduser -D -u $USER_ID -G www www -s /bin/sh

USER www
ENV HOME /home/www

EXPOSE 5000

CMD [ "gunicorn", "-w", "4", "--bind", "0.0.0.0:5000", "wsgi"]