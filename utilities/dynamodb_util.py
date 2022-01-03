import typing


def paginate_dynamodb_response(
    dynamodb_action: typing.Callable, **kwargs
) -> typing.Generator[dict, None, None]:

    # Using the syntax from https://github.com/awsdocs/aws-doc-sdk-examples/blob/main/python/example_code/dynamodb/GettingStarted/MoviesScan.py
    keywords = kwargs

    done = False
    start_key = None

    while not done:
        if start_key:
            keywords["ExclusiveStartKey"] = start_key

        response = dynamodb_action(**keywords)

        start_key = response.get("LastEvaluatedKey", None)
        done = start_key is None

        for item in response.get("Items", []):
            yield item
