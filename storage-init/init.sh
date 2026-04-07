#!/bin/sh
# storage-init/init.sh
# Runs once at startup via the storage-init container.
# Configures the MinIO `mc` client and creates required buckets.
set -e

MINIO_ENDPOINT="minio:9000"
MINIO_ALIAS="trackmcp"

# Read the root password from the Docker secret file
MINIO_ROOT_PASSWORD=$(cat /run/secrets/minio_root_password)

echo "[storage-init] Configuring mc alias..."
mc alias set "${MINIO_ALIAS}" \
    "http://${MINIO_ENDPOINT}" \
    "${MINIO_ROOT_USER}" \
    "${MINIO_ROOT_PASSWORD}" \
    --api S3v4

echo "[storage-init] Waiting for MinIO to be fully ready..."
until mc ready "${MINIO_ALIAS}" > /dev/null 2>&1; do
    echo "[storage-init] MinIO not ready yet, retrying in 3s..."
    sleep 3
done

echo "[storage-init] MinIO is ready."

# ------------------------------------------------------------------
# Create buckets
# ------------------------------------------------------------------

create_bucket() {
    BUCKET_NAME="$1"
    if mc ls "${MINIO_ALIAS}/${BUCKET_NAME}" > /dev/null 2>&1; then
        echo "[storage-init] Bucket '${BUCKET_NAME}' already exists — skipping."
    else
        echo "[storage-init] Creating bucket '${BUCKET_NAME}'..."
        mc mb "${MINIO_ALIAS}/${BUCKET_NAME}"
        echo "[storage-init] Bucket '${BUCKET_NAME}' created."
    fi
}

create_bucket "raw-files"
create_bucket "exports"

# ------------------------------------------------------------------
# Apply bucket policies
# (keep both buckets private — access via presigned URLs only)
# ------------------------------------------------------------------
mc anonymous set none "${MINIO_ALIAS}/raw-files"
mc anonymous set none "${MINIO_ALIAS}/exports"

echo "[storage-init] Bucket policy: raw-files  → private"
echo "[storage-init] Bucket policy: exports     → private"

# ------------------------------------------------------------------
# Optional: enable versioning on raw-files for safety
# ------------------------------------------------------------------
mc version enable "${MINIO_ALIAS}/raw-files" || true
echo "[storage-init] Versioning enabled on 'raw-files'."

echo "[storage-init] Done. All buckets configured successfully."
