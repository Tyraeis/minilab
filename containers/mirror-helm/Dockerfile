FROM alpine:3

RUN apk add --no-cache curl jq helm bash
USER 1000:1000
COPY --chmod=755 mirror.sh /mirror.sh
ENTRYPOINT ["/bin/bash", "/mirror.sh"]
