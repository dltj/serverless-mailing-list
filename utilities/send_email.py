""" Send a one-off email message """
import os
import boto3
from utilities.log_config import logger

ses_sender_identity = os.environ["SES_SENDER_IDENTITY_ARN"].split("/")[-1]
ses_configuration_set = os.environ["SES_CONFIGURATION_SET_ARN"].split("/")[-1]
ses = boto3.client("sesv2")


def send_email(recipient, subject, body):
    email_response = ses.send_email(
        FromEmailAddress=ses_sender_identity,
        Destination={"ToAddresses": [recipient]},
        Content={
            "Simple": {
                "Subject": {
                    "Data": subject,
                    "Charset": "UTF-8",
                },
                "Body": {"Html": {"Data": body, "Charset": "utf-8"}},
            },
        },
        ConfigurationSetName=ses_configuration_set,
    )
    logger.debug(f"AWS SES send {email_response=}")
