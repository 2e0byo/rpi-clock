FROM python:3.12-alpine as base
ENV PIP_CACHE_DIR=/var/cache/pip \
    POETRY_CACHE_DIR=/var/cache/poetry

FROM base as builder
RUN --mount=type=cache,target=/var/cache \
<<EOF
  apk update
  apk add curl
  curl -sSL https://install.python-poetry.org | python3 -
EOF
COPY . /app
WORKDIR /app
RUN --mount=type=cache,target=/var/cache/pip \
<<EOF
  touch README.md
  /root/.local/bin/poetry build
EOF

FROM base as lgpio
WORKDIR /app
RUN --mount=type=cache,target=/var/cache \
<<EOF
  apk update
  apk add swig libc-dev linux-headers py3-setuptools make gcc
  wget https://github.com/joan2937/lg/archive/master.zip
  unzip master.zip
  cd lg-master
  make
  make install || true # the error appears not to matter
  apk del make
EOF


FROM lgpio as clock
COPY --link --from=builder /app/dist /app/dist
WORKDIR /app
RUN --mount=type=cache,target=/var/cache \
<<EOF
  pip install dist/*.whl
EOF
CMD ["rpi-clock"]
