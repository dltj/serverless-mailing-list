""" Lambda handler set up a new issue to be sent """

import os
import json
import time
import re
from base64 import b64decode
import urllib.request
import urllib.error
from urllib.parse import parse_qs
from bs4 import BeautifulSoup
from utilities.log_config import logger
from utilities.jinja_renderer import site_wrap
from utilities.dynamodb_util import paginate_dynamodb_response

import boto3

dynamodb = boto3.resource("dynamodb")
issues_table = dynamodb.Table(os.environ["ISSUES_DYNAMODB_TABLE"])
subscribers_table = dynamodb.Table(os.environ["SUBSCRIBERS_DYNAMODB_TABLE"])

sqs = boto3.resource("sqs")
ses_fifo_queue = sqs.Queue(os.environ["SES_FIFO_QUEUE"])

ses_sender_identity = os.environ["SES_SENDER_IDENTITY_ARN"].split("/")[-1]
ses_configuration_set = os.environ["SES_CONFIGURATION_SET_ARN"].split("/")[-1]


def endpoint(event, context):
    logger.info(json.dumps(event))

    # Did we get POSTed content?
    if "body" in event:
        body = event["body"]
    else:
        logger.error("No POST content received")
        return site_wrap(
            title="No POST content received",
            content="<p>The <i>create_issue</i> POST needs these values:</p><ul><li><b>issue_url</b>: link to the issue HTML<li></ul>",
            statusCode=400,
        )

    if "isBase64Encoded" in event and event["isBase64Encoded"]:
        body = b64decode(body)
    body = parse_qs(body.decode())
    logger.debug(f"Form content: {body=}")

    # Is the issue URL in the posted content?
    if "issue_url" not in body:
        logger.error("issue_url not found in body")
        return site_wrap(
            title="Incomplete POST content received",
            content="<p>The <i>create_issue</i> POST needs these values:</p><ul><li><b>issue_url</b>: link to the issue HTML<li></ul>",
            statusCode=400,
        )

    if type(body["issue_url"]) is list:
        issue_url = body["issue_url"][0]
    else:
        issue_url = body["issue_url"]

    # Find the issue number embedded in the URL
    logger.debug(f"Requested {issue_url=}")
    issue_regex = re.compile(r"/issue-(\d+)-[^/]+/?$")
    issue_regex_result = issue_regex.search(issue_url)
    if issue_regex_result:
        issue_number = int(issue_regex_result.group(1))
    else:
        logger.error(f"Couldn't get issue number from  {issue_url}")
        return site_wrap(
            title="Couldn't get issue number",
            content=f"<p>Couldn't get issue number from  {issue_url}</p>",
            statusCode=400,
        )

    # Go get the HTML of the issue
    try:
        with urllib.request.urlopen(issue_url) as response:
            page_html = response.read().decode()
    except urllib.error.URLError as error:
        logger.error(f"Couldn't retrieve HTML of {issue_url}: {error.reason}")
        return site_wrap(
            title="Couldn't retrieve HTML",
            content=f"<p>Couldn't retrieve HTML of {issue_url}: {error.reason}</p>",
            statusCode=400,
        )

    # Look for the H1-tagged title and the content body
    ## FIXME: This is hard coded
    soup = BeautifulSoup(page_html, features="html.parser")
    main_content = soup.find("div", id="main").find("div", class_="page__inner-wrap")
    issue_title = main_content.find_next("h1").string.rstrip()
    issue_content = str(main_content.find_next("section"))
    if not issue_title:
        logger.error(f"Couldn't find 'issue_title' from {issue_url}")
        return site_wrap(
            title="Couldn't retrieve issue_title",
            content=f"<p>Couldn't find 'issue_title' from {issue_url}</p>",
            statusCode=400,
        )
    if not issue_content:
        logger.error(f"Couldn't find 'issue_content' from {issue_url}")
        return site_wrap(
            title="Couldn't retrieve issue_content",
            content=f"<p>Couldn't find 'issue_content' from {issue_url}</p>",
            statusCode=400,
        )
    logger.info(f"Got issue {issue_number} on '{issue_title}'")

    # Have we sent this issue already?
    issue = issues_table.get_item(Key={"issue_number": issue_number})
    logger.debug(f"DynamoDB get_item response: {issue}")
    if issue and "Item" in issue:
        logger.error(f"Issue already found: {issue['Item']=}")
        return site_wrap(
            title="Issue already found in the database",
            content=f"<p>Issue {issue_number} was already found in the database {issue['Item']}</p>",
            statusCode=500,
        )

    # Store metadata for this issue
    # issue_row = {
    #     "issue_number": issue_number,
    #     "subject": issue_title,
    #     "sentStarting": int(time.time()),
    #     "subscribers": "0",
    # }
    # logger.info(f"New issue: {issue_row=}")
    # response = issues_table.put_item(Item=issue_row)
    # logger.debug(f"DynamoDB put_item response: {response}")

    # Loop through subscribers
    for subscriber in paginate_dynamodb_response(subscribers_table.scan):
        logger.debug(f"Checking subscriber {subscriber=}")
        if (
            "subscribedAt" in subscriber
            and subscriber["subscribedAt"] > 0
            and subscriber["lastIssueSent"] != issue_number
        ):
            email_params = {
                "ConfigurationSetName": ses_configuration_set,
                "Destination": subscriber["email"],
                "FromEmailAddress": ses_sender_identity,
                "Subject": issue_title,
                "Body": issue_content,
            }
            response = ses_fifo_queue.send_message(
                MessageBody=json.dumps(email_params), MessageGroupId=str(issue_number)
            )
            logger.debug(f"Send email_params to queue: {response=}")

            subscriber["lastIssueSent"] = issue_number
            response = subscribers_table.put_item(Item=subscriber)
            logger.debug(f"Updated subscriber: {response=}")

    return site_wrap(
        title=f"Got content for Issue #{issue_number}: {issue_title}",
        content=f"<p>The content you are looking for is {issue_content}.</p>",
        statusCode=200,
    )
