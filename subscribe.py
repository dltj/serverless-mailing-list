""" Lambda handler for the subscribe form post """

import os
import json
import time
import uuid
from base64 import b64decode
from utilities.log_config import logger
from utilities.jinja_renderer import site_wrap, confirmation_email
from urllib.parse import parse_qs

import boto3
from botocore.exceptions import ClientError

BASE_PATH = os.environ["BASE_PATH"]

ses = boto3.client("sesv2")
dynamodb = boto3.resource("dynamodb")
subscribers_table = dynamodb.Table(os.environ["SUBSCRIBERS_DYNAMODB_TABLE"])

ses_sender_identity = os.environ["SES_SENDER_IDENTITY_ARN"].split("/")[-1]
ses_configuration_set = os.environ["SES_CONFIGURATION_SET_ARN"].split("/")[-1]


def endpoint(event, context):
    logger.info(json.dumps(event))

    if "body" in event:
        body = event["body"]
    else:
        return site_wrap(
            title="No email address received",
            content="<p>The form submission did not include an email address. Please try again.</p>",
            statusCode=400,
        )

    if "isBase64Encoded" in event and event["isBase64Encoded"]:
        body = b64decode(body)
    body = parse_qs(body.decode())
    logger.debug(f"Form content: {body=}")

    if "email" not in body:
        return site_wrap(
            title="Email address field not received",
            content="<p>The form submission did not include an email address. Please try again.</p>",
            statusCode=400,
        )

    if type(body["email"]) is list:
        email = body["email"][0]
    else:
        email = body["email"]

    logger.debug(f"Requested {email=}")
    subscriber = subscribers_table.get_item(Key={"email": email})
    logger.debug(f"DynamoDB get_item response: {subscriber}")
    if subscriber and "Item" in subscriber:
        logger.info(f"Subscriber found: {subscriber['Item']=}")
        return site_wrap(
            title="Hey! I think you are already subscribed!",
            content=f"<p>I have {email} on the newsletter subscription list already.  If you aren't receiving it, please get in touch so we can sort out the problem.</p>",
            statusCode=400,
        )

    subscriber = {
        "email": email,
        "id": str(uuid.uuid4()),
        "requestedAt": int(time.time()),
        "lastIssueSent": 0,
    }

    base_url = f"https://{event['requestContext']['domainName']}{BASE_PATH}"
    confirm_url = f"{base_url}/subscribe/confirm/{email}/{subscriber['id']}"
    email_body = confirmation_email(confirm_url)

    try:
        email_response = ses.send_email(
            FromEmailAddress=ses_sender_identity,
            Destination={"ToAddresses": [email]},
            Content={
                "Simple": {
                    "Subject": {
                        "Data": "Link for subscribing to the newsletter enclosed",
                        "Charset": "UTF-8",
                    },
                    "Body": {"Html": {"Data": email_body, "Charset": "utf-8"}},
                },
            },
            ConfigurationSetName=ses_configuration_set,
        )
    except ClientError as e:
        logger.error("Could not send email: %", e.response["Error"]["Message"])
        return site_wrap(
            title="Couldn't send message",
            content=f"<p>Well, this isn't good.  I couldn't send an email to {email}.  The error has been logged; please get in touch with me to sort it out.</p>",
            statusCode=500,
        )
    logger.debug(f"AWS SES send {email_response=}")

    logger.info(f"New subscriber: {subscriber=}")
    response = subscribers_table.put_item(Item=subscriber)
    logger.debug(f"DynamoDB put_item response: {response}")

    return site_wrap(
        title="Confirmation email sent",
        content=f"<p>I got your request to subscribe {email}.  Please check your email for a confirmation link.</p>",
    )
