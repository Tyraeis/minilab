FROM alpine:3

RUN apk add --no-cache curl jq helm
USER 1000:1000
COPY mirror.sh /mirror.sh --chmod=755
ENTRYPOINT ["/mirror.sh"]
