# Concert Ticketing System

A microservices-based concert ticketing system built with Docker.

## Quick Start

1. Make sure you have Docker and Docker Compose installed
2. Clone this repository
3. Copy the `.env` file provided on eLearn to the root directory of the project
   > **IMPORTANT**: Before starting the application, copy the `.env` file that was sent separately and place it in the root directory of the project. This file contains all the necessary environment variables for the services to function properly.
4. Run the application with the following command:
    docker-compose up -d --build
5. Run the frontend:From the root folder, run the following commands:
    cd UI/public
    python -m http.server 8080
6. Go to http://localhost:8080/login.html
7. Login with the following credentials:
    Email_address: breannong@gmail.com
    Password: iloveesd@2025
8. You should be able to see these events on the top row in the index.html:
    Jia Le Hokkien Hits Concert II
    j-hope Tour ‘HOPE ON THE STAGE’ in SINGAPORE
    M2M The Better Endings Tour 2025 - Singapore

    If you see "Wrong Event" in the index.html page, it is likely that one of the containers did not run 

The application will start with development-friendly defaults. All services will be available through the API Gateway at http://localhost:8000.

## Production Setup

For production deployment, create a `docker-compose.prod.yml` file with your production environment variables and run:

```bash

```

## Environment Variables

The system requires a `.env` file in the root directory containing all necessary environment variables. This file has been provided separately for security reasons. Make sure to:

1. Copy the provided `.env` file to the root directory
2. Do not modify the variables unless instructed
3. Keep the file secure and do not commit it to version control


## Stopping the Application

docker-compose down

To remove all data:
docker-compose down -v
