## Set Up Environment

1. `cd serverless-mailing-list`
1. `pipenv install --dev`
1. `pipenv run nodeenv -p`
1. `pipenv shell`

## Installation

1. Create a certificate for the domain name
1. Create a SES sender identity for Newsletter
1. Create an SES ConfigurationSet for Newsletter [not currently supported by CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ses-configurationset.html)
1. Set values in config.yml
1. Create stack: `serverless deploy --stage prod --aws-profile dltj-admin`
1. Upload templates to S3 bucket
1. Attach the SesHealth SNS topic to the Bounce and Complaint endpoints
