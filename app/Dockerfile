FROM python:3.7-slim
LABEL maintainer="Anton Lebedev <mailbox@lebster.me>"
WORKDIR /app
RUN pip install pipenv
COPY Pipfile* /tmp/
RUN cd /tmp && pipenv lock --requirements > requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY . /app
RUN mkdir -p /tmp/files/img
COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD python app.py
