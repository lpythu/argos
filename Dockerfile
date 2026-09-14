ARG NODE_IMAGE=harbor.saidc/base/saidc-node:22-pnpm11.12.0
ARG BASE_IMAGE=harbor.saidc/base/saidc-uv:0.12.0

FROM ${NODE_IMAGE} AS ui
WORKDIR /ui
COPY dash/ui/package.json dash/ui/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm npm install
COPY dash/ui/ ./
RUN npm run build

FROM ${BASE_IMAGE}
WORKDIR /app
COPY dash/pyproject.toml dash/alembic.ini dash/entrypoint.sh dash/skill.md ./
COPY dash/alembic ./alembic
COPY dash/*.py ./
COPY dash/routers ./routers
RUN --mount=type=cache,target=/root/.cache/uv \
    python -c 'import tomllib, pathlib; print("\n".join(tomllib.load(pathlib.Path("pyproject.toml").open("rb"))["project"]["dependencies"]))' \
    | uv pip install --system -r -
COPY --from=ui /ui/dist ./ui/dist
RUN chmod +x /app/entrypoint.sh
ENV PYTHONPATH=/app
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
