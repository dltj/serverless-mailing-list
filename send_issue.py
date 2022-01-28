import json
import os
import time
import traceback

import boto3
from botocore.exceptions import ClientError

from utilities.log_config import logger

message_queue = boto3.client("sqs")
ses = boto3.client("sesv2")
message_queue_empty = False

# set these at environment variables
QUEUE_URL = os.environ["SES_FIFO_QUEUE"]
# Time the Lambda will be running before shutting down. (max 5 mins)
LAMBDA_RUN_TIME = int(os.environ["SES_LAMBDA_RUN_TIME_SECONDS"]) * 1000
# The time in milliseconds to keep within a second, to ensure SES limitations are not exceeded.
THRESHOLD = 100
# charset supported in messages
CHARSET = "UTF-8"
# number of process to be invoked concurrently
PARALLEL_REQUESTS = 4
# the limitation that SES has on sending multiple emails at once
SES_SEND_RATE = int(os.environ["SES_SEND_RATE_PER_SECOND"])


def get_time_millis():
    """
    This function returns the current time in milliseconds
    :return current_time : the current time in milliseconds
    """
    current_time = int(round(time.time() * 1000))
    return current_time


def receive_messages():
    """
    This function retrieves messages from SQS
    :return response: dictionary of messages received from SQS
    """
    response = message_queue.receive_message(
        QueueUrl=QUEUE_URL,
        AttributeNames=["SentTimestamp"],
        MaxNumberOfMessages=10,
        MessageAttributeNames=["All"],
        VisibilityTimeout=20,
        WaitTimeSeconds=0,
    )

    return response


def send_email(sqs_msg_body):
    """
    This function will send an email through AWS SWS
    :param text: the message to be sent through SES
    :return response: the response received from SES
    """
    msg_details = json.loads(sqs_msg_body)
    logger.debug(f"About to send to {msg_details['Destination']=}")
    try:
        response = ses.send_email(
            FromEmailAddress=msg_details["FromEmailAddress"],
            Destination={"ToAddresses": [msg_details["Destination"]]},
            Content={
                "Simple": {
                    "Subject": {"Data": msg_details["Subject"], "Charset": CHARSET},
                    "Body": {"Html": {"Data": msg_details["Body"], "Charset": CHARSET}},
                },
            },
            ConfigurationSetName="Newsletter",
        )
    except ClientError as e:
        logger.error(f"Could not send email: {e.response['Error']['Message']}")
    else:
        logger.debug(f"Email sent: {response=}")
    return response


def delete_message(receipt_handle):
    """
    This function will delete the specified message from SQS
    :param receipt_handle: this is the handle of the message to be deleted
    """
    message_queue.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
    logger.debug(f"Message deleted: {receipt_handle=}")


def process_message(messages):
    """
    This function will process each message using a separate thread
    :param message: the message object that needs to be processed
    """

    logger.debug(f"Attempting to process {messages=}")
    for message in messages:
        try:
            send_email(message["Body"])
            delete_message(message["ReceiptHandle"])
        except Exception as error:
            tb = traceback.format_exc().replace("\n", "\r")
            logger.error("Error %s. Traceback: %s", error, tb)


def handle_sqs_messages():
    """
    This function controls the maximum send rate per second. It is designed to run for
    approximately one second.
    """
    start_time = get_time_millis()
    counter = 0

    # While we haven't overrun our per-second send rate and there is more than one second
    # left since this function invocation started
    while counter < SES_SEND_RATE and get_time_millis() - start_time + THRESHOLD < 1000:
        logger.debug(f"Inside while loop. {counter=}, {start_time=}")

        response = receive_messages()
        global message_queue_empty

        if response.get("Messages") is None:
            message_queue_empty = True
            break

        messages = response["Messages"]
        logger.debug(f"Got {len(messages)} messages")

        if SES_SEND_RATE - counter - len(messages) < 0:
            logger.debug(f"Processing partial message list: {SES_SEND_RATE - counter}")
            process_message(messages[: (SES_SEND_RATE - counter)])
            counter += len(messages)
        else:
            logger.debug(f"Processing full SES_SEND_RATE of messages")
            process_message(messages)
            counter += len(messages)

    # Sleep any remainder left of one second since the invocation of
    # this function.
    run_time = get_time_millis() - start_time
    if run_time < 1000:
        logger.debug(f"{1000 - run_time} milliseconds remaining")
        time.sleep((1000 - run_time) / 1000)


def handle_lambda_process():
    """
    This function handles the process of Lambda and stops it when needed
    """
    overall_start = get_time_millis()

    while (
        not message_queue_empty and get_time_millis() - overall_start < LAMBDA_RUN_TIME
    ):
        handle_sqs_messages()


def endpoint(event, context):
    """
    This is the handler of the lambda function
    :param event: event that triggers the lambda function
    :param context: the context in which the lambda is being run
    :return: the final status of the process
    """
    response = message_queue.get_queue_attributes(
        QueueUrl=QUEUE_URL,
        AttributeNames=["ApproximateNumberOfMessages"],
    )
    if (
        not response
        or not response["Attributes"]
        or not response["Attributes"]["ApproximateNumberOfMessages"]
    ):
        raise Exception("Couldn't read queue length")
    if response["Attributes"]["ApproximateNumberOfMessages"] == "0":
        return "Nothing to process"
    logger.debug(f"{response['Attributes']['ApproximateNumberOfMessages']=}")
    global message_queue_empty
    message_queue_empty = False
    handle_lambda_process()

    return "Lambda Process Completed"
