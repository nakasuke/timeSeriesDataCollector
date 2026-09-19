FROM tinkerpop/gremlin-server:3.8.1

COPY gremlin-server.yaml /opt/gremlin-server/conf/prototype-server.yaml
COPY tinkergraph.properties /opt/gremlin-server/conf/tinkergraph.properties
COPY prototype-init.groovy /opt/gremlin-server/scripts/prototype-init.groovy

# The base image already defines an ENTRYPOINT that invokes
# bin/gremlin-server.sh. Pass only the YAML path here; otherwise the entrypoint
# tries to parse bin/gremlin-server.sh itself as YAML.
CMD ["conf/prototype-server.yaml"]
