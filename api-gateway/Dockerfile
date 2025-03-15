FROM kong
USER root
COPY kong.yml /
USER kong
RUN cp /etc/kong/kong.conf.default /etc/kong/kong.conf