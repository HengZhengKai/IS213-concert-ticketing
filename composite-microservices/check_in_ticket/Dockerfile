FROM python:3-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY ./templates ./templates/
COPY ./invokes.py ./check_in_ticket.py ./
CMD [ "python", "./check_in_ticket.py" ]