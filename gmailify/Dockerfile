ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip

WORKDIR /app
COPY rootfs/app/requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY rootfs/ /
RUN chmod +x /run.sh

EXPOSE 8099
CMD ["/run.sh"]
