import time
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


def store_test_ids(ids: list, table_name: str) -> None:
    """Stores a count of tests at key 0 and test ids in subsequent keys.
    table_name must be unique, define table name in the main function"""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    table.put_item(Item={"key": 0, "id_count": str(len(ids))})
    for key, test_id in enumerate(ids):
        table.put_item(Item={"key": key + 1, "test_id": test_id})


def obtain_bearer_token(app_id: str, app_key: str) -> None:
    """Takes an app_id and appKey value input. Obtained from TelQ UI on a per-user level. Outputs a bearer token which is required for all future API calls"""
    url = "https://api.telqtele.com/v2/client/token"
    payload = {"appId": app_id, "appKey": app_key}
    print(f"Sending payload {payload} to {url}")
    response = requests.post(url, json=payload)
    print(f"Received response:\n{response.text}")
    return response.json()


def create_test(token: str, mcc: str, mnc: str) -> dict:
    """Tells the TelQ system that we'd like to test a specific network, outputs the first value in the response which contains the test id, 'testIdText' and destination phoneNumber.  Do error handling here since we might call this function repeatedly."""
    auth_header = {"authorization": token}
    data = {
        "destinationNetworks": [{"mcc": mcc, "mnc": mnc}],
        "testTimeToLiveInSeconds": "3600",
    }
    response = requests.post(
        "https://api.telqtele.com/v2/client/tests", headers=auth_header, json=data
    )
    output = response.json()
    try:
        output = output[0]
    except BaseException as err:
        print(
            "We seem to have received an unexpected response from TelQ. Here is what we received:"
        )
        print(response.json())
        raise err
    return output


def create_contact(env: dict, c_code: str, phone_num: str) -> str:
    """Create a contact in the TelQ org in *** with the information provided from telq. In accordance with how this was configured in ReadyAPI, we do not currently go back and delete this contact."""
    contact_data = {
        "organizationId": env["orgId"],
        "lastName": phone_num,
        "status": "A",
        "country": c_code.upper(),
        "recordTypeId": env["recordTypeId"],
        "accountId": "0",
        "externalId": phone_num,
        "paths": [
            {
                "waitTime": "0",
                "pathId": "241901148045324",
                "countryCode": c_code.upper(),
                "value": phone_num,
                "skipValidation": "false",
            }
        ],
        "firstName": "TelQ Test",
        "timezoneId": "America/New_York",
    }
    header_data = {"Authorization": env["apiKey"]}
    api_endpoint = str(env["endpoint"]) + "/rest/contacts/" + env["orgId"]
    response = requests.post(api_endpoint, headers=header_data, json=contact_data)
    create_contact_response = response.json()
    try:
        contact_id = create_contact_response["id"]
    except BaseException as err:
        print(
            "We seem to have received an unexpected response from ***. Here is what we received:"
        )
        print(response.json())
        raise err
    return contact_id


def build_notification(
    test_id: str,
    message_body: str,
    cont_id: str,
    title: str,
    confirm: bool,
    language: str,
    env: dict,
) -> str:
    """Here we put together and send the notification. Outputs the notification ID response from *** API"""
    notification_data = {
        "status": "A",
        "organizationId": env["orgId"],
        "priority": "NonPriority",
        "type": "Standard",
        "message": {
            "contentType": "Text",
            "title": title,
            "textMessage": test_id + message_body,
        },
        "broadcastContacts": {"contactIds": [cont_id]},
        "broadcastSettings": {
            "language": language,
            "confirm": confirm,
            "deliverPaths": [
                {
                    "accountId": env["accountId"],
                    "pathId": "241901148045324",
                    "organizationId": env["orgId"],
                    "id": env["deliveryId"],
                    "status": "A",
                    "seq": 1,
                    "prompt": "SMS",
                    "extRequired": "false",
                    "displayFlag": "false",
                    "default": "false",
                }
            ],
        },
        "launchtype": "SendNow",
    }
    header_data = {"Authorization": env["apiKey"]}
    api_endpoint = str(env["endpoint"]) + "/rest/notifications/" + env["orgId"]
    response = requests.post(api_endpoint, headers=header_data, json=notification_data)
    notification_response = response.json()
    try:
        notifi_id = notification_response["id"]
    except BaseException as err:
        print(
            "We seem to have received an unexpected response from ***. Here is what we received:"
        )
        print(notification_response)
        raise err
    return notifi_id


def send_notification(
    c_code: str, test_id_text: str, contact_id: str, env: dict
) -> str:
    """# Triggers the build/send of a notification based on selected notification test_type."""
    message_body = " You may have to leave your home quickly to stay safe."
    title = c_code + " Short Auto Message"
    confirm = "false"
    language = "en_US"
    notification_id = build_notification(
        test_id_text, message_body, contact_id, title, confirm, language, env
    )
    return notification_id


def main(event, context):
    """Main function invoked by lambda"""
    target_countries = ["ru", "ua"]
    test_networks = {
        "ru": [
            {"mcc": "250", "mnc": "20"},
            {"mcc": "250", "mnc": "99"},
            {"mcc": "250", "mnc": "02"},
            {"mcc": "250", "mnc": "01"},
        ],
        "ua": [
            {"mcc": "255", "mnc": "01"},
            {"mcc": "255", "mnc": "06"},
            {"mcc": "255", "mnc": "03"},
        ],
    }
    tests_per_network = 3
    unique_table_name = "****************"

    print(f"Received event:\n{event}")
    print(f"Received context:\n{context}")
    secrets = get_secret()
    environment = {
        "name": "Prod US",
        "apiKey": secrets["***_API_Key"],
        "orgId": "****************",
        "recordTypeId": "****************",
        "accountId": "****************",
        "deliveryId": "****************",
        "endpoint": "https://api.****************.net",
    }
    telq_test_ids = []

    try:
        token_request = obtain_bearer_token(secrets["app_id"], secrets["app_key"])
        bearer_token = token_request["value"]
    except BaseException as err:
        print("There was an error obtaining an auth token.")
        print("Here is the response received from TelQ:")
        print(token_request)
        raise err
    else:
        print("Successfully Obtained Auth Token")

    for target in target_countries:
        country_networks = test_networks[target]
        for test_network in country_networks:
            test_count = 0
            while test_count < tests_per_network:
                test = create_test(
                    bearer_token, test_network["mcc"], test_network["mnc"]
                )
                id_num = str(test["id"])
                telq_test_ids.append(id_num)
                test_id_text = str(test["testIdText"])
                phone_number = str(test["phoneNumber"])
                print("Successfully created TelQ Test...")
                contact_id = create_contact(environment, target, phone_number)
                time.sleep(1)
                print("Successfully created *** Contact...")
                notification_id = send_notification(
                    target, test_id_text, contact_id, environment
                )
                time.sleep(1)
                print("Successfully sent notification Test...")
                print(notification_id)
                test_count += 1
                time.sleep(1)
    store_test_ids(telq_test_ids, unique_table_name)
