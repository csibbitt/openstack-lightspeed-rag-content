#!/usr/bin/env python
# coding: utf-8

from argparse import ArgumentParser
import json
import multiprocessing as mp

import requests
from tqdm import tqdm


def get_jira_data(
    jira_url: str, headers: dict, query: str, max_results: int, start_at: int
):
    """Retrieve data from JIRA"""
    full_url = f"{jira_url}/rest/api/2/search?jql={query}&maxResults={max_results}&fields=*all&startAt={start_at}"
    print(f"Getting: {full_url}")
    try:
        response = requests.get(
            full_url,
            headers=headers,
            timeout=(3.05, 180),
        )

    except requests.exceptions.Timeout:
        print(f"Request to {jira_url} failed with time out.")
        return []

    if response.status_code == 200:
        data = json.loads(response.text)
    else:
        print(f"Couldn't retrieve data from JIRA {response.status_code} for {full_url}")
        return []

    return data["issues"]


def update_database(
    jira_token: str,
    max_results: int = 10000,
    jira_url: str = "https://issues.redhat.com",
    jira_database_bkp_path: str = "jira_all_bugs.pickle",
):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {jira_token}",
    }
    results = []

    # projects = "&OR&".join([f"project={e}" for e in jira_projects])
    # query = f"{projects}&AND&type=bug&AND&status=Closed"
    query = "assignee=csibbitt-rh ORDER by createdDate DESC"
    # Get initial batch of data
    try:
        response = requests.get(
            f"{jira_url}/rest/api/2/search?jql={query}&maxResults={max_results}&fields=*all",
            headers=headers,
            timeout=(3.05, 180),
        )
    except requests.exceptions.Timeout as e:
        print(f"Request to {jira_url} failed with time out.")
        raise e

    if response.status_code == 200:
        data = json.loads(response.text)
    else:
        print(f"Couldn't retrieve any data from JIRA {response.status_code}")
        raise ValueError

    total = data["total"]
    print(f"{total} items found for query {query}")

    # Retrieve results going further back
    with mp.Pool(10) as pool:
        results = pool.starmap(
            get_jira_data,
            [
                (jira_url, headers, query, max_results, page)
                for page in range(1000, total, 1000)
            ],
        )

    results.append(data["issues"])

    # Flatten the list of issues
    results = [issue for e in results for issue in e]

    dataset = []

    for raw_result in tqdm(results):
        row = {}
        row["id"] = raw_result["id"]
        row["url"] = f"{jira_url}/browse/{raw_result['key']}"
        row["summary"] = raw_result["fields"]["summary"]
        row["description"] = raw_result["fields"]["description"]
        row["comments"] = "\n\n".join(
            [comment["body"] for comment in raw_result["fields"]["comment"]["comments"]]
        )
        dataset.append(row)

        # Write the row to a file
        with open("jira-plaintext/" + raw_result["key"] + ".txt", "w") as file:
            file.write(
                f"# {row['summary']}\n\n{row['description']}\n\n{row['comments']}"
            )


def main():
    parser = ArgumentParser("jira_scraper")
    parser.add_argument("--jira_url", type=str, default="https://issues.redhat.com")
    parser.add_argument("--jira_token", type=str)
    parser.add_argument("--max_results", type=int, default=1000)
    args = parser.parse_args()

    update_database(
        jira_token=args.jira_token,
        max_results=args.max_results,
        jira_url=args.jira_url,
    )


if __name__ == "__main__":
    main()
