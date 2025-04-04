FROM python:3-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY ./waitlist.py .
COPY .env .
CMD [ "python", "./waitlist.py" ]