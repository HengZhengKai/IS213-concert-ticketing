FROM python:3-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY ./invokes.py ./buy_resale_ticket.py ./
CMD [ "python", "./buy_resale_ticket.py" ]