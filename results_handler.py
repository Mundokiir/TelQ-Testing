from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import make_msgid
import smtplib
import json
import requests
import boto3


def get_secret() -> dict:
    """Retrieves the various keys from AWS secrets manager"""
    secret_name = "****************"
    region_name = "****************"

    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    secret = get_secret_value_response["SecretString"]

    return json.loads(secret)


def lookup_test_ids(table_name: str) -> list:
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    response = table.get_item(Key={"key": 0})
    test_count = int(response["Item"]["id_count"])
    test_ids = []
    for index in range(1, test_count + 1):
        response = table.get_item(Key={"key": index})
        test_ids.append(response["Item"]["test_id"])
    print(test_ids)
    return test_ids


def obtain_bearer_token(app_id, app_key):
    print("obtaining bearer token")
    url = "https://api.telqtele.com/v2/client/token"
    payload = {"appId": app_id, "appKey": app_key}
    response = requests.post(url, json=payload)
    output = response.json()
    return output["value"]


def get_test_results(testid, token):
    url = f"https://api.telqtele.com/v2/client/results/{testid}"
    auth_header = {"authorization": token}
    response = requests.get(url, headers=auth_header)
    output = response.json()
    test_profile = {}
    test_profile["id"] = output["id"]
    test_profile["countryName"] = output["destinationNetworkDetails"]["countryName"]
    test_profile["providerName"] = output["destinationNetworkDetails"]["providerName"]
    if output["testStatus"] == "POSITIVE":
        test_profile["textDelivered"] = output["textDelivered"]
        test_profile["receiptDelay"] = f"{output['receiptDelay']} seconds"
        test_profile["testStatus"] = "DELIVERED"
        test_profile["receivedFrom"] = output["senderDelivered"]
    else:
        test_profile["textDelivered"] = "N/A"
        test_profile["receiptDelay"] = "N/A"
        test_profile["testStatus"] = output["testStatus"]
        test_profile["receivedFrom"] = "N/A"
    return test_profile


def main(event, context):
    """Main function invoked by lambda"""
    report_name = "Ukraine and Russia TelQ Testing Report"
    smtp_server = "****************.com"
    field_list = [
        "id",
        "countryName",
        "providerName",
        "textDelivered",
        "receivedFrom",
        "testStatus",
        "receiptDelay",
    ]
    results_in_email = True
    attach_csv = False
    results_in_email_count = 0
    testing_mode = False
    email_from = "****************"
    email_to = ["****************", "****************"]
    unique_table_name = "****************"

    print(f"Received event:\n{event}")
    print(f"Received context:\n{context}")
    secrets = get_secret()
    bearer_token = obtain_bearer_token(secrets["app_id"], secrets["app_key"])
    final_test_results = []
    testid_list = lookup_test_ids(unique_table_name)
    for test in testid_list:
        final_test_results.append(get_test_results(test, bearer_token))

    if attach_csv is True:
        with open("results.csv", "wt", encoding="UTF-8") as csv_file:
            # Write the first header row
            first_row = ",".join(field_list)
            csv_file.write(first_row + "\n")
            csv_file.close()
            # Re-open in append mode for adding further rows
        with open("results.csv", "at", encoding="UTF-8") as csv_file:
            # Iterate through each result (row), fill in missing values, add a comma after, and combine each
            for row in final_test_results:
                new_line = ""
                for key in field_list:
                    if key not in row:
                        row[key] = ""
                    new_line = new_line + '"' + str(row[key]) + '"' + ","
                # Write our row to the file, minus the last comma, and add a new line
                csv_file.write(new_line[:-1] + "\n")
            csv_file.close()

    if results_in_email is False:
        message = f"<html>\n<head></head>\n<body>\n<p>{report_name}</p>\n\n<p>Please see attached CSV file.</p>\n</body>\n</html>\n"
    else:
        message = ""
        counter = results_in_email_count + 1
        for row in final_test_results:
            newlist = []
            if results_in_email_count != 0:
                counter -= 1
            else:
                counter += 1  # Just increase the count, no biggie
            if counter > 0:
                for key in field_list:
                    if key not in row:
                        row[key] = ""
                    row[key] = str(row[key])
                    newlist.append(
                        f'<td style="border: 1px solid black; border-collapse: collapse;">{row[key]}</td>\n'
                    )
                message = message + "<tr>\n" + "".join(newlist) + "</tr>\n"

        email_headers = [
            f'<th style="border: 1px solid black; border-collapse: collapse;">{x}</th>\n'
            for x in field_list
        ]
        if results_in_email_count != 0:
            header_header = f'<html>\n<head></head>\n<body>\n<p>Here is the data for: {report_name}.<br />\nA sample of {results_in_email_count} rows of data is shown here. See attached CSV for full results.</p>\n<table style="width:100%; border: 1px solid black; border-collapse: collapse;">\n<thead>\n<tr>\n'
        else:
            header_header = f'<html>\n<head></head>\n<body>\n<p>Here is the data for the {report_name} report. Total records found: {counter - 1}</p>\n<table style="width:100%; border: 1px solid black; border-collapse: collapse;">\n<thead>\n<tr>\n'
        header_body = "".join(email_headers)
        header_footer = "</tr>\n</thead>\n<tbody>\n"
        message_header = header_header + header_body + header_footer
        message_footer = "</tbody>\n</table>\n</body>\n</html>"
        message = message_header + message + message_footer

    # Create the email message.
    to_list = []
    for address in email_to:
        to_list.append(Address(addr_spec=address))
    msg = EmailMessage()
    msg["Subject"] = report_name
    msg["From"] = email_from
    msg["To"] = tuple(to_list)
    # In case recipient isn't viewing in html for some reason
    msg.set_content(report_name + "\n\nPlease see attached CSV file.")
    asparagus_cid = make_msgid()
    msg.add_alternative(
        message.format(asparagus_cid=asparagus_cid[1:-1]), subtype="html"
    )
    # note that we needed to peel the <> off the msgid for use in the html.

    if attach_csv is True:
        csv_file = open("results.csv", "r", encoding="UTF-8").read()
        msg.add_attachment(csv_file, filename="results.csv")

    # Connect to the mail server and send the message
    if testing_mode is True:
        print(message)
    else:
        server = smtplib.SMTP(smtp_server, 25)
        server.ehlo()
        server.send_message(msg)
        server.quit()
    return
