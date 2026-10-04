# City Facts API
## What it does

City Facts API is a small HTTP service that provides information about cities.
It supports listing cities, checking service health, and retrieving information
about a specific city by name.
## Requirements

* Java 21
* Gradle

## Run

The service uses the `PORT` environment variable.

```bash
PORT=8080 ./scripts/run.sh
```

If `PORT` is not specified, the service uses port `8080`.

## Test

Run the automated tests with:

```bash
./scripts/test.sh
```

The test script checks the main endpoints and prints the result in the format:

```text
TESTS: 4/4
```

## Endpoints

### GET /

Returns the list of available cities.

### GET /healthz

Health check endpoint. Returns `200 OK` when the service is running.

### GET /cities/{name}

Returns information about a city.

Example:

```text
GET /cities/Almaty
```

An unknown city returns `404 Not Found`.

## Port

The application listens on the port specified by the `PORT` environment variable.

Default:

```text
8080
```
