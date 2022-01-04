""" Lambda handler for the subscribe confirmation link """

import os
import json
import time
from utilities.log_config import logger
from utilities.jinja_renderer import site_wrap, email_template
from utilities.send_email import send_email

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
subscribers_table = dynamodb.Table(os.environ["SUBSCRIBERS_DYNAMODB_TABLE"])

BASE_PATH = os.environ["BASE_PATH"]


def endpoint(event, context):
    logger.info(json.dumps(event))

    if (
        "pathParameters" in event
        and "email" in event["pathParameters"]
        and "identifier" in event["pathParameters"]
    ):
        email = event["pathParameters"]["email"]
        identifier = event["pathParameters"]["identifier"]
    else:
        logger.error(f"Incorrectly formatted confirmation URL...missing pathParameters")
        return site_wrap(
            title="Incorrectly formatted confirmation URL",
            content="<p>This shouldn't happen.  The error details have been logged, and if you would kindly get in touch with me I will help you subscribe.</p>",
            statusCode=400,
        )

    sub_query = subscribers_table.get_item(Key={"email": email})
    logger.debug(f"DynamoDB get_item response: {sub_query}")
    if not sub_query or "Item" not in sub_query:
        logger.error("DynamoDB did not return the subscriber Item")
        return site_wrap(
            title="Subscription database error",
            content="<p>This shouldn't happen.  The error details have been logged, and if you would kindly get in touch with me I will help you subscribe.</p>",
            statusCode=500,
        )
    subscriber = sub_query["Item"]

    if identifier != subscriber["id"]:
        logger.warning(f"Subscriber's identifier didn't match...got {subscriber['id']}")
        return site_wrap(
            title="Problem with the email confirmation",
            content="<p>Sorry—that confirmation link was incorrect.  Please review the link in the email I sent you.</p>",
            statusCode=400,
        )

    subscriber["subscribedAt"] = int(time.time())

    logger.info(f"Confirmed subscriber: {subscriber=}")
    response = subscribers_table.put_item(Item=subscriber)
    logger.debug(f"DynamoDB put_item response: {response}")

    h1_header = "Thank you for subscribing to DLTJ's Thursday Threads"
    body_content = """
    <p style="margin: 0 0 10px;">Each Thursday, you'll receive the best of what I'm reading as well as threads to past news and conversations.</p>
    <p style="margin: 0 0 10px;">If you ever want to unsubscribe, simply follow the unsubscribe link at the bottom of each email.</p>
    """
    base_url = f"https://{event['requestContext']['domainName']}{BASE_PATH}"
    unsubscribe_url = f"{base_url}/unsubscribe/{email}/{subscriber['id']}"
    email_body = email_template(
        h1_header=h1_header,
        body_content=body_content,
        preheader="Interesting news and useful commentary will be in your inbox every Thursday.",
        unsubscribe_url=unsubscribe_url,
    )

    try:
        send_email(email, h1_header, email_body)
    except ClientError as e:
        logger.error("Could not send email: %", e.response["Error"]["Message"])
        return site_wrap(
            title="Couldn't send message",
            content=f"<p>Well, this isn't good.  I couldn't send an email to {email}.  The error has been logged; please get in touch with me to sort it out.</p>",
            statusCode=500,
        )

    return site_wrap(
        title="Subscription confirmed! Welcome to the Newsletter",
        content=f"<p>Thanks for subscribing.</p>",
    )
