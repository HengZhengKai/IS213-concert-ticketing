FROM python:3-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY ./task.py ./

# Create a shell script to start both services
RUN echo '#!/bin/bash\n\
celery -A task.celery worker --loglevel=INFO &\n\
sleep 5\n\
python ./task.py\n\
' > start.sh && chmod +x start.sh

# Default to running both
CMD ["./start.sh"]