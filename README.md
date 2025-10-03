# pricechecker
Checks whether products are on sale at Woolworths or Coles

## Installation

Build the docker image using the supplied Dockerfile:

```
docker build -t pricechecker:latest .
```

Deploy using the supplied docker compose file:

```
docker compose up
```

The default port is set to `8888`

## Configuration

A `config.ini` file is required with the following format:

```
[Gmail]
address = your.email@gmail.com
password = your_app_password
```

## Adding Products

Navigate to the web page (e.g. `http://localhost:8888`) to search and add products.