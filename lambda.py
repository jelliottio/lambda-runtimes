"""
AWS Lambda Runtime Inventory Tool

Purpose:
    Collect Lambda function runtime information across multiple AWS accounts
    and regions using configured AWS CLI profiles.

Output:
    Generates a JSON report grouped by:
        Account -> Region -> Runtime -> Lambda Functions

Example use cases:
    - Identify deprecated Lambda runtimes
    - Plan runtime upgrades
    - Audit serverless environments
"""

import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.exceptions import ClientError, ProfileNotFound


# AWS CLI profile names configured locally
AWS_ACCOUNTS = [
    "dev",
    "pipeline",
    "prod",
    "special",
]

# Regions to scan
REGIONS = [
    "us-east-1",
    "us-west-2",
    "eu-west-1",
]

OUTPUT_FILE = "lambda_functions_report.json"


# Configure application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def get_lambda_functions(account: str, region: str) -> dict:
    """
    Retrieve Lambda functions for a specific AWS account and region.

    Returns:
        Dictionary grouped by Lambda runtime:
        {
            "python3.11": [
                "function-a",
                "function-b"
            ],
            "nodejs18.x": [
                "function-c"
            ]
        }
    """

    try:
        # Create a session using the AWS CLI profile for the account
        session = boto3.Session(
            profile_name=account,
            region_name=region,
        )

        lambda_client = session.client("lambda")

        functions_by_runtime = defaultdict(list)

        # Lambda list_functions is paginated, so use a paginator
        paginator = lambda_client.get_paginator("list_functions")

        for page in paginator.paginate():
            for function in page.get("Functions", []):

                # Container image Lambda functions do not have Runtime
                runtime = function.get("Runtime", "Image")

                functions_by_runtime[runtime].append(
                    function["FunctionName"]
                )

        # Sort output to make reports consistent and easier to review
        return {
            runtime: sorted(function_names)
            for runtime, function_names in sorted(
                functions_by_runtime.items()
            )
        }

    except ProfileNotFound:
        logging.error(
            "AWS profile '%s' was not found.",
            account,
        )

    except ClientError as error:
        logging.error(
            "AWS API error for %s/%s: %s",
            account,
            region,
            error,
        )

    except Exception as error:
        logging.error(
            "Unexpected error for %s/%s: %s",
            account,
            region,
            error,
        )

    return {
        "error": "Unable to retrieve Lambda functions"
    }


def collect_lambda_inventory() -> dict:
    """
    Collect Lambda runtime information from all accounts and regions.

    Uses ThreadPoolExecutor because each AWS API request is independent
    and can run concurrently.
    """

    results = {}

    # Build a list of all account/region combinations
    scan_targets = [
        (account, region)
        for account in AWS_ACCOUNTS
        for region in REGIONS
    ]

    with ThreadPoolExecutor(max_workers=10) as executor:

        # Submit AWS queries concurrently
        futures = {
            executor.submit(
                get_lambda_functions,
                account,
                region,
            ): (account, region)
            for account, region in scan_targets
        }

        # Process completed requests
        for future in as_completed(futures):
            account, region = futures[future]

            logging.info(
                "Completed scan: %s / %s",
                account,
                region,
            )

            results.setdefault(account, {})

            results[account][region] = future.result()

    return results


def save_report(data: dict) -> None:
    """
    Write collected Lambda inventory data to JSON.
    """

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=4,
        )

    logging.info(
        "Report saved to %s",
        OUTPUT_FILE,
    )


def main():
    """
    Application entry point.
    """

    logging.info("Starting Lambda inventory collection")

    inventory = collect_lambda_inventory()

    save_report(inventory)

    logging.info("Lambda inventory collection complete")


if __name__ == "__main__":
    main()
