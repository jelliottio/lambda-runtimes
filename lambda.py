# Python script to gather lambda runtimes from multiple AWS accounts and regions.
import boto3
import json


aws_accounts = ["dev", "pipeline", "prod", "special"]
regions = ["us-east-1", "us-west-2", "eu-west-1"]


def get_lambda_functions(account, region):
    session = boto3.Session(profile_name=account, region_name=region)
    lambda_client = session.client("lambda")

    try:
        functions = []
        paginator = lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            functions.extend(page["Functions"])

        grouped_functions = {}
        for func in functions:
            runtime = func["Runtime"]
            if runtime not in grouped_functions:
                grouped_functions[runtime] = []
            grouped_functions[runtime].append(func["FunctionName"])

        return grouped_functions

    except Exception as e:
        print(
            f"Error fetching Lambda functions for account: {account}, region: {region}. Error: {e}"
        )
        return None


def gather_lambda_data():
    results = {}

    for account in aws_accounts:
        results[account] = {}
        for region in regions:
            print(f"Fetching data for account: {account}, region: {region}...")
            lambda_data = get_lambda_functions(account, region)
            if lambda_data:
                results[account][region] = lambda_data
            else:
                results[account][region] = {"error": "Failed to fetch data"}

    with open("lambda_functions_report.json", "w") as file:
        json.dump(results, file, indent=4)

    print("Data collection complete. Results saved to lambda_functions_report.json")


if __name__ == "__main__":
    gather_lambda_data()
