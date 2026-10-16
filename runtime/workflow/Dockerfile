FROM node@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS node
FROM python@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && npm install --global cline@3.0.70 \
 && python -m pip install --no-cache-dir jsonschema==4.26.0 pytest==8.4.2 \
 && mkdir /inputs /work /out \
 && chmod 555 /inputs /work \
 && chown 1000:1000 /out
ENV PYTHONDONTWRITEBYTECODE=1 HOME=/tmp/home
USER 1000:1000
WORKDIR /work
CMD ["python", "--version"]
USER 0
COPY probe.py /usr/local/libexec/workflow_probe.py
RUN mkdir /inputs/contracts && printf 'allowed\n' > /inputs/contracts/allowed.txt && touch /work/owned.txt && chown 1000:1000 /work/owned.txt && chmod 555 /work && chmod 444 /inputs/contracts/allowed.txt
USER 1000:1000
