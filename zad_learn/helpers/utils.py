import boto3
from botocore.exceptions import NoCredentialsError
from django.conf import settings
from django.core.exceptions import ValidationError


def upload_to_s3(file, s3_path):
    """Upload a file to S3 and return the S3 URL."""
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    bucket_name = settings.ZAD_TRAIN_BUCKET

    try:
        s3.upload_fileobj(file, bucket_name, s3_path)
        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_path}"
        return s3_url
    except FileNotFoundError:
        raise Exception("The file was not found.")
    except NoCredentialsError:
        raise Exception("Credentials not available.")


def material_file_size(value):
    max_size = 20 * 1024 * 1024  # 20 MB
    if value.size > max_size:
        raise ValidationError("File too large. Size should not exceed 20 MB.")
