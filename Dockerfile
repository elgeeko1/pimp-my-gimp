##################
## base stage
##################

# Derive from an official Flask Docker image
FROM python:latest AS BASE

USER root

# Preconfigure debconf for non-interactive installation - otherwise complains about terminal
# Avoid ERROR: invoke-rc.d: policy-rc.d denied execution of start.
ARG DEBIAN_FRONTEND=noninteractive
ARG DISPLAY localhost:0.0
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections
RUN dpkg-divert --local --rename --add /sbin/initctl
RUN ln -sf /bin/true /sbin/initctl
RUN echo "#!/bin/sh\nexit 0" > /usr/sbin/policy-rc.d

# configure apt
RUN apt-get update -q
RUN apt-get install --no-install-recommends -y -q apt-utils 2>&1 \
	| grep -v "debconf: delaying package configuration"
RUN apt-get install --no-install-recommends -y -q ca-certificates

# install prerequisites
RUN apt-get install --no-install-recommends -y -q i2c-tools
RUN apt-get install --no-install-recommends -y -q libgpiod-dev
RUN apt-get install --no-install-recommends -y -q rpi.gpio-common
RUN apt-get install --no-install-recommends -y -q ffmpeg

# apt cleanup
RUN apt-get autoremove -y -q
RUN apt-get -y -q clean
RUN rm -rf /var/lib/apt/lists/*

# python requirements
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt /app/
RUN pip install \
    --user \
    --no-warn-script-location \
    --no-cache-dir \
    -r requirements.txt


####################
## application stage
####################
FROM scratch
COPY --from=BASE / /
LABEL maintainer="elgeeko1"

EXPOSE 80/tcp

USER root

# change to match your local zone.
# matching container to host timezones synchronizes
# last.fm posts, filesystem write times, and user
# expectations for times shown in the Roon client.
ARG TZ="America/Los_Angeles"
ENV TZ=${TZ}
RUN echo "${TZ}" > /etc/timezone \
	&& ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime \
	&& dpkg-reconfigure -f noninteractive tzdata

WORKDIR /app

# copy application files into the container
COPY pimp-my-gimp.py /app/
COPY site /app/
RUN chmod +x /app/pimp-my-gimp.py

ENV DISPLAY localhost:0.0
ENTRYPOINT ["python", "-u", "/app/pimp-my-gimp.py"]