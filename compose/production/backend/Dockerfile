###########
# BUILDER #
###########

ARG PYTHON_VERSION=3.10

FROM python:${PYTHON_VERSION} as python

FROM python as python-build-stage

ARG BUILD_ENVIRONMENT=server
ARG APP_HOME=/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg2 dependencies
  libpq-dev

# install dependencies
COPY src/requirements/base.txt src/requirements/base.txt
COPY src/requirements/server.txt src/requirements/${BUILD_ENVIRONMENT}.txt
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r src/requirements/${BUILD_ENVIRONMENT}.txt


#########
# FINAL #
#########

# pull official base image
FROM python as python-run-stage

ARG BUILD_ENVIRONMENT=server
ARG APP_HOME=/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR ${APP_HOME}/src


RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg2 dependencies
  libpq-dev

COPY --from=python-build-stage /app/wheels /wheels
COPY --from=python-build-stage /app/src/requirements /requirements
RUN pip install --no-cache /wheels/*

COPY ./compose/production/backend/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/production/backend/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

COPY . $APP_HOME


ENTRYPOINT ["/entrypoint"]
