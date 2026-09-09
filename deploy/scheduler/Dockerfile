# Job de reposição/limpeza: substitui os systemd timers. Roda o crond do
# busybox (já vem no Alpine base — o pacote `dcron` separado trava com
# "setpgid: Operation not permitted" quando roda como PID 1 em container)
# e chama os endpoints do serviço `api` pela rede interna do Compose.
FROM alpine:3.20
RUN apk add --no-cache curl
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
