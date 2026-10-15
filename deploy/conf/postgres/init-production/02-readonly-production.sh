#!/bin/sh
# Only runs when the production PostgreSQL data directory is empty.
# Reuses the reviewed read-only grants while taking credentials from .env.
set -eu

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_READONLY_USER:?POSTGRES_READONLY_USER is required}"
: "${POSTGRES_READONLY_PASSWORD:?POSTGRES_READONLY_PASSWORD is required}"

case "$POSTGRES_READONLY_USER" in
  *[!a-zA-Z0-9_]*|'') echo 'Invalid read-only username' >&2; exit 1 ;;
esac
case "$POSTGRES_READONLY_PASSWORD" in
  *[!a-zA-Z0-9_]*|'') echo 'Invalid read-only password' >&2; exit 1 ;;
esac

{
  printf "\\set ro_user '%s'\n" "$POSTGRES_READONLY_USER"
  printf "\\set ro_password '%s'\n" "$POSTGRES_READONLY_PASSWORD"
  sed '/^\\set ro_user /d; /^\\set ro_password /d' /opt/guazi/02-readonly.sql
} | psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v ON_ERROR_STOP=1
