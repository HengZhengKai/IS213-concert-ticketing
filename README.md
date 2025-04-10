# Concert Ticketing System

A microservices-based concert ticketing system built with Docker.

## Quick Start

1. Make sure you have Docker and Docker Compose installed

2. Clone this repository

3. For the 3rd scenario (check in QR code) to work, make sure your laptop and your 3rd party scanner (e.g. your phone) are both connected on the same network
  - SMU Wifi Network does not work. If you running this in SMU, you can try to your phone's mobile data and use your laptop to connect to your data via HotSpot.
  - Turn off Microsoft Defender Firewall from your private network settings

4. Run the application in the root folder with the following command:
- On Windows:
  .\start-containers.ps1
- On Mac:
  ./start-containers.sh

5. Run the frontend:From the root folder, run the following commands:
    cd UI/public
    python -m http.server 8080

6. Go to http://localhost:8080/login.html

7. Login with the following credentials:
    Email_address: breannong@gmail.com
    Password: iloveesd@2025

8. You should be able to see these events on the top row in the index.html:
    Jia Le Hokkien Hits Concert II
    j-hope Tour 'HOPE ON THE STAGE' in SINGAPORE
    M2M The Better Endings Tour 2025 - Singapore

    If you see "Wrong Event" in the index.html page, it is likely that one of the containers did not run properly. Here's how to troubleshoot:

    1. Check container status:
       docker-compose ps

    2. View logs for specific services:
       docker-compose logs <service_name>
       # Service names are in this format: event-service, user-service, buy-ticket-service etc.

    3. If a container keeps restarting:
       docker-compose logs <service_name> --tail=100

    4. Common issues:
       - Database connection problems: Check if the database container is running
       - Environment variables: Verify .env file is properly configured
       - Port conflicts: Ensure no other services are using the required ports
       - Memory issues: Check if Docker has enough resources allocated

    5. To restart specific services:
       docker-compose restart <service_name>

    6. To rebuild and restart a specific service:
       docker-compose up -d --build <service_name>

The application will start with development-friendly defaults. All services will be available through the API Gateway at http://localhost:8000.

## Production Setup

For production deployment, we have prepared Kubernetes configurations. While we didn't have time to fully integrate the Kubernetes setup, the configurations are available for future deployment:

Prerequisites:
- Ensure Docker Kubernetes is running on your system
- Verify kubectl is properly configured to communicate with your cluster

1. Apply Kubernetes configurations:
   kubectl apply -f k8s/

2. View running pods:
   kubectl get pods

3. View service status:
   kubectl get services

4. View deployment status:
   kubectl get deployments

The Kubernetes configurations include:
- Deployment configurations for all microservices
- Service definitions for internal and external access
- ConfigMaps for environment variables
- Persistent volume claims for data storage

Note: The Kubernetes setup requires additional configuration of your cluster and may need adjustments based on your specific infrastructure requirements.

## Credentials
When trying out the checkout page, use the following credentials:
- Credit Card: 4242 4242 4242 4242
- Name, CVC and Expiry Date can be any value

## Environment Variables

The system requires a `.env` file in the root directory containing all necessary environment variables to run the application. This file is not publicly available for security reasons. Feel free to contact one of us if you require the file!

## Stopping the Application

docker-compose down

To remove all data:
docker-compose down -v

Remember to turn back on your private network Firewall once you are done!
