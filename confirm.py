""" Lambda handler for the subscribe confirmation link """

import os
import json
import time
from utilities.log_config import logger
from utilities.jinja_renderer import site_wrap, confirmation_email

import boto3

dynamodb = boto3.resource("dynamodb")
subscribers_table = dynamodb.Table(os.environ["SUBSCRIBERS_DYNAMODB_TABLE"])


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

    subscriber["subscribedAt"] = str(time.time())

    logger.info(f"Confirmed subscriber: {subscriber=}")
    response = subscribers_table.put_item(Item=subscriber)
    logger.debug(f"DynamoDB put_item response: {response}")

    return site_wrap(
        title="Subscription confirmed! Welcome to the Newsletter",
        content=f"<p>Thanks for subscribing.</p>",
    )
