import subprocess
import logging
from threading import Lock

import boto3
from botocore.exceptions import BotoCoreError, ClientError, ProfileNotFound
from fastapi import HTTPException

from .config import Settings


_LOGIN_LOCK = Lock()
logger = logging.getLogger("agentic-workspace-chat.aws")


def _profile_session(config: Settings):
    return boto3.Session(profile_name=config.aws_profile, region_name=config.aws_region)


def authenticated_session(config: Settings):
    """Return a usable AWS session, establishing SSO in the backend terminal if needed."""
    if config.aws_auth_mode.lower() == "keys":
        if not config.aws_access_key_id or not config.aws_secret_access_key:
            raise HTTPException(503, "AWS_AUTH_MODE=keys requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return boto3.Session(
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            aws_session_token=config.aws_session_token,
            region_name=config.aws_region,
        )
    if not config.aws_profile:
        raise HTTPException(503, "AWS_PROFILE must be set when AWS_AUTH_MODE=sso")

    try:
        logger.info("AWS session check profile=%s region=%s", config.aws_profile, config.aws_region)
        session = _profile_session(config)
        session.client("sts").get_caller_identity()
        logger.info("AWS session ready source=cache")
        return session
    except ProfileNotFound as error:
        raise HTTPException(503, f"AWS profile '{config.aws_profile}' was not found") from error
    except (BotoCoreError, ClientError) as initial_error:
        if not config.aws_sso_auto_login:
            raise HTTPException(503, "AWS SSO session is unavailable and automatic login is disabled") from initial_error

    # Only one request may start the interactive browser/device login. Other
    # requests wait, then reuse the refreshed CLI cache.
    with _LOGIN_LOCK:
        logger.warning("AWS SSO session unavailable; checking refreshed cache before login")
        try:
            refreshed = _profile_session(config)
            refreshed.client("sts").get_caller_identity()
            logger.info("AWS session ready source=concurrent_refresh")
            return refreshed
        except ProfileNotFound as error:
            raise HTTPException(503, f"AWS profile '{config.aws_profile}' was not found") from error
        except (BotoCoreError, ClientError):
            pass

        try:
            logger.warning("AWS SSO login starting profile=%s timeout_seconds=%s", config.aws_profile, config.aws_sso_login_timeout_seconds)
            completed = subprocess.run(
                ["aws", "sso", "login", "--profile", config.aws_profile],
                check=False,
                timeout=config.aws_sso_login_timeout_seconds,
            )
        except FileNotFoundError as error:
            raise HTTPException(503, "AWS CLI v2 is required for automatic SSO login") from error
        except subprocess.TimeoutExpired as error:
            raise HTTPException(503, "AWS SSO login timed out in the backend terminal") from error
        if completed.returncode != 0:
            logger.error("AWS SSO login failed return_code=%s", completed.returncode)
            raise HTTPException(503, "AWS SSO login failed in the backend terminal")

        try:
            refreshed = _profile_session(config)
            refreshed.client("sts").get_caller_identity()
            logger.info("AWS session ready source=sso_login")
            return refreshed
        except (BotoCoreError, ClientError, ProfileNotFound) as error:
            raise HTTPException(503, "AWS SSO login completed but the session is still unavailable") from error
