""" Lambda handler for the unsubscribe confirmation link """

import os
import json
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
        logger.error(f"Incorrectly formatted unsubscribe URL...missing pathParameters")
        return site_wrap(
            title="Incorrectly formatted unsubscribe link",
            content="<p>That link is incorrect.  Please check the unsubscribe link that it is at the bottom of each issue, or get in touch with me and I can help.</p>",
            statusCode=400,
        )

    sub_query = subscribers_table.get_item(Key={"email": email})
    logger.debug(f"DynamoDB get_item response: {sub_query}")
    if not sub_query or "Item" not in sub_query:
        logger.error("DynamoDB did not return the subscriber Item")
        return site_wrap(
            title="Subscription database error",
            content="<p>I couldn't find your email address in the subscriber database.  This shouldn't happen if you used an 'unsubscribe' link at the bottom of a newsletter email (and you haven't previously unsubscribed).  The error details have been logged, and if you would kindly get in touch with me I will help you subscribe.</p>",
            statusCode=500,
        )
    subscriber = sub_query["Item"]

    if identifier != subscriber["id"]:
        logger.warning(f"ID mismatch. expected {subscriber['id']}, got {identifier}")
        return site_wrap(
            title="Problem with the unsubscribe link",
            content="<p>That link is incorrect.  Please check the unsubscribe link that it is at the bottom of each issue, or get in touch with me and I can help.</p>",
            statusCode=400,
        )

    logger.info(f"Unsubscribe request: {subscriber=}")
    try:
        response = subscribers_table.delete_item(
            Key={"email": email}, ReturnValues="ALL_OLD"
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error("DynamoDB couldn't find the Subscriber to delete")
            return site_wrap(
                title="Subscription database error",
                content="<p>This shouldn't happen.  The error details have been logged, and if you would kindly get in touch with me I will help you subscribe.</p>",
                statusCode=500,
            )
    logger.debug(f"DynamoDB delete_item response: {response}")

    email_h1_header = "You've been unsubscribed from DLTJ's Thursday Threads"
    base_url = f"https://{event['requestContext']['domainName']}{BASE_PATH}"
    resubscribe_url = f"{base_url}/"
    email_body_content = f"""
    <p style="margin: 0 0 10px;">Thank you for reading; your email address has been removed.</p>
    <p style="margin: 0 0 10px;">If this is a mistake, you can resubscribe at <a href="{resubscribe_url}">{resubscribe_url}</a>.</p>
    """
    email_body = email_template(
        h1_header=email_h1_header,
        body_content=email_body_content,
        preheader="Unsubscribe successful.",
    )

    try:
        send_email(email, email_h1_header, email_body)
    except ClientError as e:
        logger.error("Could not send email: %", e.response["Error"]["Message"])

    return site_wrap(
        title="Unsubscribe confirmed",
        content="<p>Your email address has been removed.  Thank you for reading.</p>",
    )
