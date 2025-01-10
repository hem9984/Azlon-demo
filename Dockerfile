FROM ghcr.io/restackio/restack:main

USER root
RUN apt-get update && apt-get install -y socat

COPY run.sh /run.sh
# Ensure no \r line endings, ensure +x
RUN chmod +x /run.sh

ENTRYPOINT ["/run.sh"]
