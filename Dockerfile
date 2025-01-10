FROM ghcr.io/restackio/restack:main

USER root
RUN apt-get update && apt-get install -y socat

COPY run.sh /run.sh
# Convert line endings just in case (dos2unix):
RUN apt-get install -y dos2unix && dos2unix /run.sh
RUN chmod +x /run.sh

ENTRYPOINT ["/run.sh"]
