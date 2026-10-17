
# FileWiz API Reference Guide

This document provides a comprehensive overview of the FileWiz microservices, their authentication mechanisms, rate limiting policies, and asynchronous job handling.

## Architecture Overview

FileWiz is comprised of several microservices, each operating on specific ports:

*   **Auth Service**: Port 3001
*   **API Gateway**: Port 4001
*   **Processing Service**: Port 5001

These services work in tandem to provide a robust and scalable file management solution.

## Authentication Mechanisms

FileWiz supports multiple authentication methods to secure its endpoints:

*   **Bearer JWTs**: For stateless authentication, clients should include an `Authorization` header with a JWT token.
    Example: `Authorization: Bearer <your_jwt_token>`
*   **Cookie Sessions**: For web applications, session management is handled via HTTP cookies. Ensure cookies are passed with requests.
*   **X-API-Key**: A custom header used for API key authentication.
    Example: `X-API-Key: <your_api_key>`
*   **Internal Service Keys**: Used for inter-service communication, typically not exposed to external clients.

## Rate Limiting

To ensure fair usage and prevent abuse, FileWiz employs rate limiting. Clients exceeding the rate limit will receive a `429 Too Many Requests` status code.

*   **Retry-After Header**: The `429` response will include a `Retry-After` header indicating how many seconds the client should wait before making another request.
*   **Sliding Window**: Rate limiting is implemented using a sliding window algorithm to provide a more accurate measure of request rates over time.

## Asynchronous Job Lifecycle

FileWiz utilizes an asynchronous job processing model for long-running operations. The lifecycle of a job progresses through the following states:

*   **PENDING**: The job has been created but not yet started.
*   **PROCESSING**: The job is currently being executed by the processing service.
*   **COMPLETED**: The job has finished successfully.
*   **FAILED**: The job execution encountered an error.
*   **CANCELLED**: The job was intentionally stopped before completion.

## Endpoints and Examples

### Authentication Endpoints (Auth Service - Port 3001)

*   **POST /auth/signup**
    *   Description: Registers a new user.
    *   Request Body:
        ```json
        {
          "username": "newuser",
          "password": "securepassword",
          "email": "newuser@example.com"
        }
        ```
    *   Example:
        ```bash
        curl -X POST "http://localhost:3001/auth/signup" \
             -H "Content-Type: application/json" \
             -d '{"username": "newuser", "password": "securepassword", "email": "newuser@example.com"}'
        ```

*   **POST /auth/login**
    *   Description: Authenticates a user and returns JWT tokens.
    *   Request Body:
        ```json
        {
          "username": "existinguser",
          "password": "correctpassword"
        }
        ```
    *   Example:
        ```bash
        curl -X POST "http://localhost:3001/auth/login" \
             -H "Content-Type: application/json" \
             -d '{"username": "existinguser", "password": "correctpassword"}'
        ```

*   **POST /auth/refresh**
    *   Description: Refreshes JWT tokens using a refresh token.
    *   Request Body:
        ```json
        {
          "refreshToken": "your_refresh_token"
        }
        ```
    *   Example:
        ```bash
        curl -X POST "http://localhost:3001/auth/refresh" \
             -H "Content-Type: application/json" \
             -d '{"refreshToken": "your_refresh_token"}'
        ```

### Protected Resource Endpoint (API Gateway - Port 4001)

*   **GET /protected/resource**
    *   Description: Accesses a resource requiring authentication.
    *   Authentication: Bearer JWT or Cookie Session.
    *   Example (using JWT):
        ```bash
        curl -X GET "http://localhost:4001/protected/resource" \
             -H "Authorization: Bearer <your_access_token>"
        ```
    *   Example (using Cookie - assuming login sets a session cookie):
        ```bash
        curl -X GET "http://localhost:4001/protected/resource" \
             -H "Cookie: session=<your_session_cookie>"
        ```

### Job Management Endpoints (API Gateway - Port 4001)

*   **POST /api/v1/jobs**
    *   Description: Creates a new asynchronous job.
    *   Request Body: (Depends on the specific job type, e.g., compression settings)
        ```json
        {
          "type": "COMPRESS_PDF",
          "parameters": {
            "inputFile": "path/to/input.pdf",
            "outputFile": "path/to/output.pdf",
            "quality": 80
          }
        }
        ```
    *   Example:
        ```bash
        curl -X POST "http://localhost:4001/api/v1/jobs" \
             -H "Authorization: Bearer <your_access_token>" \
             -H "Content-Type: application/json" \
             -d '{
                   "type": "COMPRESS_PDF",
                   "parameters": {
                     "inputFile": "path/to/input.pdf",
                     "outputFile": "path/to/output.pdf",
                     "quality": 80
                   }
                 }'
        ```

*   **GET /api/v1/jobs/{jobId}**
    *   Description: Retrieves the status and details of a specific job.
    *   Example:
        ```bash
        curl -X GET "http://localhost:4001/api/v1/jobs/a1b2c3d4-e5f6-7890-1234-567890abcdef" \
             -H "Authorization: Bearer <your_access_token>"
        ```

### Specific Task Endpoints (Processing Service - Port 5001, via API Gateway)

*   **POST /compress/pdf**
    *   Description: Initiates a PDF compression task. This endpoint is likely proxied through the API Gateway.
    *   Request Body:
        ```json
        {
          "inputFile": "s3://bucket/document.pdf",
          "quality": 75
        }
        ```
    *   Example (via API Gateway):
        ```bash
        curl -X POST "http://localhost:4001/compress/pdf" \
             -H "Authorization: Bearer <your_access_token>" \
             -H "Content-Type: application/json" \
             -d '{\
                   "inputFile": "s3://bucket/document.pdf",\n                   "quality": 75\n                 }'
        ```

### Health Check Endpoints (API Gateway - Port 4001)

*   **GET /health/liveness**
    *   Description: Checks if the service is running and responsive.
    *   Example:
        ```bash
        curl -X GET "http://localhost:4001/health/liveness"
        ```
