FROM python:3-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY ./email_service.py .
COPY .env .
CMD [ "python", "./email_service.py" ]