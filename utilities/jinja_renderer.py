""" Helper functions for rendering content through Jinja """
import os
import boto3
import jinja2

TEMPLATE_BUCKET = os.environ["TEMPLATE_BUCKET"]

HTML_PAGE_FILE = "site-wrapper.j2.html"
EMAIL_TEMPLATE = "email-template.j2.html"

j2_env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath="/tmp"))
s3 = boto3.resource("s3")


def site_wrap(title, content, statusCode=200):
    """
    Wrap the HTML content in the site template and generate an API Gateway response for Lambda
    https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html#http-api-develop-integrations-lambda.response

    :param title: Plain text to be put in the <title> and <h1> tags
    :param content: HTML fragment to be inserted into the template
    :param statusCode: HTTP response status code (default=200)

    :return: AWS HTTP API Lambda Response dictionary
    """
    response_body = _load_template(HTML_PAGE_FILE).render(title=title, content=content)
    response = {
        "statusCode": statusCode,
        "headers": {"Content-type": "text/html"},
        "body": response_body,
    }
    return response


def email_template(
    h1_header,
    body_content,
    preheader=None,
    action_url=None,
    action_text=None,
    blog_version_url=None,
    unsubscribe_url=None,
):
    email_body = _load_template(EMAIL_TEMPLATE).render(
        h1_header=h1_header,
        body_content=body_content,
        preheader=preheader,
        action_url=action_url,
        action_text=action_text,
        blog_version_url=blog_version_url,
        unsubscribe_url=unsubscribe_url,
    )
    return email_body


def _load_template(template):
    local_filename = "/tmp/" + template
    if not os.path.exists(local_filename):
        s3.Bucket(TEMPLATE_BUCKET).download_file(template, local_filename)
    return j2_env.get_template(template)
