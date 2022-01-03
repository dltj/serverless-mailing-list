"""
Lambda handler the automated dyanmodb backup

Code based on work by Masudur Rahaman Sayem, solutions architect at Amazon Web Services.
* [A serverless solution to schedule your Amazon DynamoDB On-Demand Backup | AWS Database Blog](https://aws.amazon.com/blogs/database/a-serverless-solution-to-schedule-your-amazon-dynamodb-on-demand-backup/)
* [awslabs/dynamodb-backup-scheduler](https://github.com/awslabs/dynamodb-backup-scheduler)
"""

import os
import json
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
from utilities.log_config import logger

ddb = boto3.client("dynamodb")

ddb_tables = [
    os.environ["ISSUES_DYNAMODB_TABLE"].split("/")[-1],
    os.environ["SUBSCRIBERS_DYNAMODB_TABLE"].split("/")[-1],
]
days_to_look_backup = int(os.environ["DYNAMODB_BACKUP_RETENTION_DAYS"])
backup_name = "Automated serverless-mailing-list backup"


def endpoint(event, context):
    logger.info(json.dumps(event))

    for table in ddb_tables:
        try:
            # create backup
            response = ddb.create_backup(TableName=table, BackupName=backup_name)
            logger.info(f"Backup started for {table}: {response=}")

            # check recent backup
            lowerDate = datetime.now() - timedelta(days=days_to_look_backup)
            upperDate = datetime.now()
            responseLatest = ddb.list_backups(
                TableName=table,
                TimeRangeLowerBound=datetime(
                    lowerDate.year, lowerDate.month, lowerDate.day
                ),
                TimeRangeUpperBound=datetime(
                    upperDate.year, upperDate.month, upperDate.day
                ),
            )
            latest_backup_count = len(responseLatest["BackupSummaries"])
            logger.info(f"Total backup count in recent days: {latest_backup_count}")

            delete_upper_date = datetime.now() - timedelta(days=days_to_look_backup + 1)
            logger.debug(f"{delete_upper_date=}")
            # TimeRangeLowerBound is the release of Amazon DynamoDB Backup and Restore - Nov 29, 2017
            response = ddb.list_backups(
                TableName=table,
                TimeRangeLowerBound=datetime(2017, 11, 29),
                TimeRangeUpperBound=datetime(
                    delete_upper_date.year,
                    delete_upper_date.month,
                    delete_upper_date.day,
                ),
            )

            # check whether latest backup count is more than two before removing the old backup
            if latest_backup_count >= 2:
                if "LastEvaluatedBackupArn" in response:
                    last_eval_backup_arn = response["LastEvaluatedBackupArn"]
                else:
                    last_eval_backup_arn = ""

                while last_eval_backup_arn != "":
                    for record in response["BackupSummaries"]:
                        backup_arn = record["BackupArn"]
                        ddb.delete_backup(BackupArn=backup_arn)
                        logger.info(f"Deleted this backup: {backup_arn}")

                    response = ddb.list_backups(
                        TableName=table,
                        TimeRangeLowerBound=datetime(2017, 11, 23),
                        TimeRangeUpperBound=datetime(
                            delete_upper_date.year,
                            delete_upper_date.month,
                            delete_upper_date.day,
                        ),
                        ExclusiveStartBackupArn=last_eval_backup_arn,
                    )
                    if "LastEvaluatedBackupArn" in response:
                        last_eval_backup_arn = response["LastEvaluatedBackupArn"]
                    else:
                        last_eval_backup_arn = ""
            else:
                logger.debug("Recent backup does not meet the deletion criteria")

        except ClientError as e:
            logger.error(f"Boto client error {e=}")

        except ValueError as ve:
            logger.error(f"Value error {ve=}")
